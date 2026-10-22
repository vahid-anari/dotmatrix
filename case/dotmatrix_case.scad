// Desk case for the Dot Matrix display: two MAX7219 4-in-1 boards (64 x 8 LEDs)
// and an ESP32-C3 Super Mini.
//
// Parts (print each in the orientation it's exported in):
//   shell  - front and sides; prints face down, no supports
//   back   - back cover with the ESP32 holder; prints flat
//   foot   - print 2; they tilt the case back on the desk
//
// Export:  openscad -D 'part="shell"' -o shell.stl dotmatrix_case.scad
// Preview: part="all" (assembled, with the display and the ESP32 shown).
//
// The shell is about 290 mm long: on a 256 mm bed (Bambu A1, P1S, X1) lay it
// diagonally. All sizes are in mm.

part = "all";  // all | shell | back | foot | section

// ---------------------------------------------------------------- display
// Typical FC-16 sizes. Measure yours and put the numbers here.
disp_len   = 256.0;  // the two boards side by side
disp_h     = 32.0;   // height of a board
led_depth  = 9.0;    // front of the LEDs to the front of the PCB
pcb_t      = 1.6;
behind_pcb = 6.0;    // chips and pins on the back of the PCB
fit        = 0.4;    // play around the display

// ------------------------------------------------------------------- case
wall       = 2.4;    // side walls
face       = 2.0;    // front face
lip        = 1.0;    // how far the face overlaps the display's edge
acrylic    = 2.0;    // room for a tinted acrylic sheet behind the face (0 = none)
back_space = 14.0;   // room behind the display for wires
back_t     = 2.4;    // back cover
end_room   = 18.0;   // a compartment at each end: screws, and the ESP32 on the right
tilt       = 10;     // the feet lean the case back this much

// ESP32-C3 Super Mini
esp_w = 18.0;  esp_l = 22.6;  esp_t = 1.6;     // board
usb_w = 9.2;   usb_h = 3.4;                     // USB-C socket at one short end

// M3 screws into printed holes
screw_hole = 2.6;    // in the bosses: the screw cuts its own thread
screw_free = 3.4;    // in the back cover
head_d     = 6.0;
boss       = 7.0;

$fn = 40;
include <preview_text.scad>

// ------------------------------------------------------------ derived sizes
in_len   = disp_len + 2 * fit + 2 * end_room;
in_h     = disp_h + 2 * fit;
pcb_y    = face + acrylic + led_depth;               // front of the PCB
in_depth = acrylic + led_depth + pcb_t + behind_pcb + back_space;
out_len  = in_len + 2 * wall;
out_h    = in_h + 2 * wall;
out_d    = face + in_depth + back_t;
win_len  = disp_len - 2 * lip;
win_h    = disp_h - 2 * lip;
// screw positions (x from the centre, z from the bottom), in the end rooms
sx = in_len / 2 - boss / 2;
sz = [wall + boss / 2, out_h - wall - boss / 2];

// ==================================================================== shell
// Coordinates: x along the length (centred), y from the front (0) to the back,
// z up from the bottom.
module shell() {
    difference() {
        translate([-out_len / 2, 0, 0]) cube([out_len, out_d, out_h]);
        // inside, open at the back
        translate([-in_len / 2, face, wall]) cube([in_len, out_d, in_h]);
        // LED window
        translate([-win_len / 2, -1, wall + fit + lip]) cube([win_len, face + 2, win_h]);
    }
    // acrylic stops: small ledges so the sheet can't slide into the end rooms
    if (acrylic > 0)
        for (s = [-1, 1])
            translate([s * (disp_len / 2 + fit + 0.75) - 0.75, face, wall])
                cube([1.5, acrylic, in_h]);
    // screw bosses, front to back, in the corners of the end rooms
    for (s = [-1, 1], z = sz)
        translate([s * sx, face, z])
            difference() {
                hull() {
                    translate([-boss / 2, 0, -boss / 2]) cube([boss, in_depth, boss]);
                }
                rotate([-90, 0, 0]) translate([0, 0, in_depth - 12]) cylinder(d = screw_hole, h = 13);
            }
    // end stops: keep the display from sliding sideways into the end rooms
    for (s = [-1, 1], z = [wall, out_h - wall - 2])
        translate([s * (disp_len / 2 + fit) + (s < 0 ? -3 : 0), face, z])
            cube([3, acrylic + led_depth, 2]);
}

// ================================================================ back cover
module back_cover() {
    difference() {
        union() {
            translate([-in_len / 2 + fit, 0, wall + fit]) cube([in_len - 2 * fit, back_t, in_h - 2 * fit]);
            // ribs that hold the display against the face (top and bottom edge of the PCB)
            rib = back_space + behind_pcb;  // reaches exactly to the back of the PCB
            for (z = [wall + fit + 0.4, out_h - wall - fit - 0.4 - 1.6])
                translate([-disp_len / 2 + 8, -rib, z]) cube([disp_len - 16, rib, 1.6]);
            // ESP32 holder: two rails the board slides between, USB-C towards the cover
            esp_holder();
        }
        // screw holes with countersunk heads
        for (s = [-1, 1], z = sz)
            translate([s * sx, 0, z]) rotate([-90, 0, 0]) {
                translate([0, 0, -1]) cylinder(d = screw_free, h = back_t + 2);
                translate([0, 0, back_t - 1.4]) cylinder(d1 = screw_free, d2 = head_d, h = 1.41);
            }
        // USB-C opening
        translate([esp_x(), -1, out_h / 2]) rotate([-90, 0, 0])
            hull() for (d = [-1, 1]) translate([0, d * (usb_w - usb_h) / 2, 0])
                cylinder(d = usb_h + 1.6, h = back_t + 2);
        // vent slots
        for (i = [-5:5])
            translate([i * 18 - 6, -1, out_h / 2 - 7]) cube([12, back_t + 2, 2]);
        for (i = [-5:5])
            translate([i * 18 - 6, -1, out_h / 2 + 5]) cube([12, back_t + 2, 2]);
    }
}

// The ESP32 stands on its long edge in the right end room, USB-C pointing back.
function esp_x() = disp_len / 2 + fit + end_room / 2 - 2;

module esp_holder() {
    rail_len = 14;
    for (d = [-1, 1])
        translate([esp_x() + d * (esp_t / 2 + 0.25) + (d < 0 ? -1.6 : 0), -rail_len, out_h / 2 - esp_w / 2 - 1])
            difference() {
                cube([1.6, rail_len, esp_w + 2]);
            }
    // a shelf under the board
    translate([esp_x() - 3, -rail_len, out_h / 2 - esp_w / 2 - 1 - 1.6]) cube([6, rail_len, 1.6]);
}

// ===================================================================== foot
foot_w = 30;  foot_len = 60;  foot_h = 16;  pocket = 8;
// Leaning back lowers the case's back edge; the pocket's front is raised by
// that much, so the case sits fully in it.
pocket_z = foot_h - pocket + out_d * sin(tilt);
pocket_y = foot_len / 2 - out_d / 2 + 2;

module foot() {
    difference() {
        hull() {
            translate([0, 0, 0]) cube([foot_w, foot_len, 4]);
            translate([0, 8, 0]) cube([foot_w, foot_len - 16, foot_h]);
        }
        // the case sits in this tilted pocket
        translate([-1, pocket_y, pocket_z])
            rotate([-tilt, 0, 0]) translate([0, -0.3, 0]) cube([foot_w + 2, out_d + 0.6, 40]);
    }
}

// =============================================================== the parts
module display_dummy() {
    color("darkgreen") translate([-disp_len / 2, pcb_y, wall + fit]) cube([disp_len, pcb_t, disp_h]);
    color([0.15, 0.05, 0.05]) translate([-disp_len / 2, face + acrylic, wall + fit]) cube([disp_len, led_depth, disp_h]);
    // a few lit LEDs, so the picture looks like the real thing
    for (x = [0:63], y = [0:7]) if (floor(preview_cols[x] / pow(2, y)) % 2 == 1)
        color([1, 0.3, 0.2]) translate([-disp_len / 2 + 2 + x * 4, face + acrylic - 0.05, wall + fit + disp_h - 2 - y * 4])
            rotate([-90, 0, 0]) cylinder(d = 3, h = 0.6, $fn = 12);
    color("dimgray") translate([-disp_len / 2 + 30, pcb_y + pcb_t, wall + fit + 8]) cube([disp_len - 60, behind_pcb, disp_h - 16]);
}

module esp_dummy() {
    color("navy") translate([esp_x() - esp_t / 2, out_d - back_t - esp_l, out_h / 2 - esp_w / 2]) cube([esp_t, esp_l, esp_w]);
    color("silver") translate([esp_x() - usb_h / 2, out_d - back_t - 7, out_h / 2 - usb_w / 2]) cube([usb_h, 7, usb_w]);
}

if (part == "shell") {
    rotate([90, 0, 0]) shell();  // face down on the bed
} else if (part == "back") {
    translate([0, 0, back_t]) rotate([-90, 0, 0]) back_cover();  // outside down
} else if (part == "foot") {
    foot();
} else if (part == "section") {
    // The right end, cut open through the ESP32.
    intersection() {
        assembled();
        translate([esp_x(), -100, -100]) cube([200, 300, 300]);  // cut through the ESP32
    }
} else {
    assembled();
}

module assembled() {
    // Assembled, standing on its feet and leaning back by `tilt`.
    fx = in_len / 2 - 40;
    for (s = [-1, 1]) translate([s * fx - foot_w / 2, 0, 0]) color("#2b2f33") foot();
    translate([0, pocket_y, pocket_z]) rotate([-tilt, 0, 0]) {
        color("#3a4046") shell();
        color("#59616a") translate([0, out_d - back_t, 0]) back_cover();
        display_dummy();
        esp_dummy();
        if (acrylic > 0) color([0.1, 0.1, 0.1, 0.25])
            translate([-disp_len / 2 - fit, face, wall]) cube([disp_len + 2 * fit, acrylic - 0.1, in_h]);
    }
}

echo(str("case: ", out_len, " x ", out_d, " x ", out_h, " mm (length x depth x height)"));
