// Case for the Dot Matrix display: two MAX7219 FC-16 boards (64 x 8 LEDs),
// an ESP32-C3 Super Mini, and the optional GY-BME280 and GY-302 (BH1750)
// sensors. It stands upright on a shelf.
//
// Two printed parts, both exported in print orientation (set `part`):
//   case   - the body, front face on the bed. 310.6 x 38.4 x 25.7: on a 256 mm
//            bed (Bambu A1) turn it diagonally in the slicer.
//   cover  - the back cover, outside on the bed. Holds the ESP32's USB end.
// Test pieces, to check the fit first: test_frame (the front's first 2 mm),
// test_end / test_cover (the right end: ESP32, light sensor, USB),
// test_end_l / test_cover_l (the left end: BME280).
// Pictures: all (put together), open (cover off), section (cut through the
// right end).
//
// The display slides in from the back, then the ESP32 into its frame on the
// right end wall (under two lips at its front corners), and the sensors.
// Screws: 10 x M3x6 button head. The cover takes 8 of them in M3 brass
// heat-set inserts (4.2 x 5); the light sensor's 2 go straight into plastic.
//
// Frame: x along the length (centred, the display's IN end at +x), y up
// (0 = underside), z from the front face (0) to the back. All in mm; the
// display, ESP32 and sensor sizes were measured.
//
// Needs the partbin models: git submodule update --init (case/partbin).

use <partbin/displays/max7219_fc16/max7219_fc16.scad>
use <partbin/dev-boards/esp32_c3_supermini/esp32_c3_supermini.scad>
use <partbin/sensors/gy_bme280/gy_bme280.scad>
use <partbin/sensors/gy302_bh1750/gy302_bh1750.scad>

part = "all";       // case | cover | test_frame | test_end | test_cover | test_end_l | test_cover_l | all | open | section
one_piece = true;   // case and cover each printed whole

// ------------------------------------------------- display (measured)
block    = 31.7;   // one LED block, wide (measured)
gap      = 1.5;    // between two blocks, also where the two boards meet (measured, about)
disp_len = 8 * block + 7 * gap;   // 264.1: both boards (each 4 blocks: 131.3 measured)
disp_h   = 31.9;   // blocks and the blue boards are the same height (measured)
led      = 11.1;   // front of the LEDs to the front of the blue board (12.6 to its back, measured)
pcb      = 1.5;    // (measured)
green    = 1.9;    // the green perfboard strips behind the joint (3.4 with the board, measured)
green_x  = 38;     // they reach this far each side of the joint (from the photo)
green_y  = 12;     // and this far in from the top and bottom edges (from the photo)
fit      = 0.25;   // play around the display in the window
film     = 0;      // recess in the front for a film (0: none; a stick-on tint film goes over the whole front). The LED face sits at its floor
fin_w    = 1.0;    // fins between the blocks that hold the board from the front
fin_in   = 3.0;    // how far they reach in from the top and bottom

// ------------------------------------------------------------------- case
wall     = 3.0;    // end walls (as thick as the top and bottom)
wall_tb  = 3.0;    // top and bottom walls: the middle screws' heads sink into them
face     = 1.6;    // front
rear     = 13.1;   // board back to the cover's inside: deep enough for the ESP32 standing front to back
cover_t  = 2.4;
end_room = 20.0;   // at each end: BME280 (left); light sensor + ESP32 (right)
with_stand = false; // it sits upright on a shelf at eye level; true adds the tilted desk stand
tilt     = 10;     // (stand) leans back this much on the desk
base_d   = 48;     // stand depth on the desk, from the front edge
base_t   = 3;

// screws: M3 button head; the cover's into M3 brass heat-set inserts
// (4.2 OD x 5: hole 4.0 x 5.5 in an 8 mm boss), M3x6 through the 2.4 cover
pilot   = 2.5;
free_d  = 3.4;
boss_d  = 8.0;
ins_d   = 4.0;
ins_l   = 5.5;

$fn = 40;

// ---------------------------------------------------------- derived sizes
in_len  = disp_len + 2 * fit + 2 * end_room;
in_h    = disp_h + 2 * fit;
out_len = in_len + 2 * wall;
out_h   = in_h + 2 * wall_tb;
z_led   = film;                     // LED front
z_pcb   = z_led + led;              // PCB front
z_pback = z_pcb + pcb;              // PCB back
z_in    = z_pback + rear;           // cover inside face
out_d   = z_in + cover_t;
y0      = wall_tb;                  // inside bottom
y1      = wall_tb + in_h;           // inside top
xe      = in_len / 2;               // inside end
xd      = disp_len / 2 + fit;       // display end (+ fit)
part_x  = -(xe - 9);                // partition, left end: the BME280 room is outside it

// ESP32 (right end, on the right cover, USB out through the right end wall)
// ESP32: standing on the right end wall, its long edges in two rails, parts
// facing in, USB-C out through the cover. It slides in from the back.
esp_off = 1.5;                      // end wall to the board's back (room for solder joints)
esp_yc  = y0 + in_h / 2;            // board centre (height)
esp_z1  = z_in - 0.2;               // board back edge; the socket reaches 1.7 past it, into the cover
esp_cl  = 0.15;                     // play around the board in its frame
fr_t    = 1.2;                      // frame walls
esp_xb  = xe - esp_off;             // board back face
usb_xc  = esp_xb - 0.8 - 1.55;      // USB socket centre
usb_yc  = esp_yc - 0.4;             // the socket sits 0.4 off the board centre

// light sensor: behind the front of the right end, in front of the ESP32, looking forward
ls_x    = xd + 0.3 + 13.9 / 2;
ls_y    = y0 + in_h / 2;            // board centre
ls_post = 3.6;                      // front wall to the board's face: an M3x6 through the board gets 4.4 mm (0.8 left in front)
ls_chip = 18.5 / 2 - 6.5;           // BH1750 chip above the board centre (partbin)
// where the blocks meet: the fins go here
gaps = [for (k = [1:7]) -disp_len / 2 + k * (block + gap) - gap / 2];

// BME280: in a frame on the left end wall like the ESP32, its sensor facing
// the wall 2 mm from the vents, pins at the back. It slides in from the back
// and two fingers on the cover keep it there.
bme_w    = 15.3;                    // board, across (y) (measured)
bme_l    = 11.7;                    // board, front to back (z) (measured)
bme_gap  = 2.0;                     // end wall to the board's parts side (chip 0.93)
bme_y    = y0 + in_h / 2;
bme_zf   = out_d / 2 - bme_l / 2;   // board front edge: the board (and its vents) centred on the end wall's depth
bme_xp   = -xe + bme_gap;           // board's parts side
bme_xb   = bme_xp + 1.5;            // board's back side (1.5 measured)
bme_top  = bme_zf + bme_l - 3;      // the whole frame stops 3 mm short of the wire end

// cover screws: [x, y]; bosses run from the cover forward. All alike: they
// hang from the top or bottom wall and start just behind the display board
// with a 45 degree underside. Pairs above each other, mirrored left/right.
end_bx = ls_x;                      // the end-room pairs, over the light sensor's centre
// Only in the end rooms: behind the display nothing may hang from the top or
// bottom wall, or the display can't be put in from the back.
bosses = [[-end_bx, y0 + 4], [-end_bx, y1 - 4], [end_bx, y1 - 4], [end_bx, y0 + 4]];
function full_depth(b) = false;

// The middle of the cover: tabs on the cover reach forward along the top and
// bottom walls (behind the display board, so they don't get in the way when
// the display goes in first). M3x6 from outside through the wall into an
// insert in each tab; the head sinks into a pocket in the 3 mm wall.
mid_x   = 66;
mids    = [for (x = [-mid_x, mid_x], top = [false, true]) [x, top]];
tab_z0  = z_pback + 1.1;            // tab front end
tab_t   = 6.5;                      // tab thickness off the wall (insert 5.5 + 1)
tab_w   = 8;
mid_z   = (tab_z0 + z_in) / 2;      // screw axis (depth)
module mid_tab(m) translate([m[0] - tab_w / 2, m[1] ? y1 - 0.1 - tab_t : y0 + 0.1, tab_z0]) cube([tab_w, tab_t, z_in - tab_z0 + 0.01]);
module mid_insert(m) translate([m[0], m[1] ? y1 - 0.1 + 0.01 : y0 + 0.1 - 0.01, mid_z]) rotate([m[1] ? 90 : -90, 0, 0]) cylinder(d = ins_d, h = ins_l + 0.01);
// The case prints front face down, so these holes run sideways: teardrop
// shaped, pointing up in the print (case +z), so their tops need no bridge.
module teardrop(d, h, dir) linear_extrude(h) hull() {
    circle(d = d);
    translate([0, dir * d / 2 * sqrt(2)]) square(0.01, center = true);
}
module mid_screw_hole(m) translate([m[0], m[1] ? out_h + 0.1 : -0.1, mid_z]) rotate([m[1] ? 90 : -90, 0, 0]) {
    cylinder(d = free_d, h = wall_tb + 0.3);   // round: a little sag doesn't matter, the screw opens it
    teardrop(6.2, 1.8 + 0.1, m[1] ? 1 : -1);    // pocket for the button head (1.65)
}
function boss_z0(b) = z_pback + 0.2;   // where a boss starts

// ================================================================ the box
module box() {
    difference() {
        union() {
            difference() {
                translate([-out_len / 2, 0, 0]) cube([out_len, out_h, z_in]);
                translate([-xe, y0, face]) cube([in_len, in_h, out_d]);
                window();
                bme_vents();
                ls_window();
                film_recess();
                for (m = mids) mid_screw_hole(m);
            }
            partition();
            for (b = bosses) boss(b);
            fins();
            esp_mount();
            ls_mounts();
            bme_frame();
        }
        for (b = bosses) translate([b[0], b[1], z_in - ins_l]) cylinder(d = ins_d, h = ins_l + 0.01);   // inserts
        for (p = ls_holes()) translate([p[0], p[1], 0.8]) cylinder(d = pilot, h = face + ls_post);   // M3 (its holes are 3 mm)
    }
}

// The opening: the display's own size plus play, so nothing covers the LEDs.
// The display sits in it with its face at the floor of the film recess.
module window() translate([-xd, y0, -0.01]) cube([2 * xd, in_h, face + 0.02]);

// A shallow recess around the window for the film, taped at its edges.
module film_recess() if (film > 0) translate([-xd - 3, y0 - 1.4, -0.01]) cube([2 * xd + 6, in_h + 2.8, film + 0.01]);

// Fins in the gaps between the blocks, from the top and bottom walls back to
// the blue board: they keep the display from coming out at the front.
module fins() for (x = gaps, top = [false, true])
    translate([x - fin_w / 2, top ? y1 - fin_in : y0 - 0.01, z_led]) cube([fin_w, fin_in + 0.01, z_pcb - z_led]);

// A screw boss. In the end rooms it runs the full depth; behind the display it
// starts 0.2 behind the PCB and widens at 45 degrees from the wall, so it
// prints with the front face on the bed.
module boss(b) {
    top = b[1] > out_h / 2;
    wy = top ? y1 : y0;                // the wall it grows from
    if (full_depth(b)) {
        translate([b[0], b[1], face - 0.01]) cylinder(d = boss_d, h = z_in - face + 0.01);
        translate([b[0] - boss_d / 2, top ? b[1] : wy - 0.5, face - 0.01]) cube([boss_d, abs(b[1] - wy) + 0.5, z_in - face + 0.01]);
    } else {
        z0 = boss_z0(b);
        reach = abs(b[1] - wy) + boss_d / 2;           // how far it stands off the wall
        hull() {
            translate([b[0], b[1], z0 + reach]) cylinder(d = boss_d, h = z_in - z0 - reach);
            translate([b[0] - boss_d / 2, top ? wy - 0.01 : wy - 0.01, z0]) cube([boss_d, 0.02, 0.01]);
        }
        // and joined to the wall along its length
        translate([b[0] - boss_d / 2, top ? b[1] : wy - 0.5, z0 + reach])
            cube([boss_d, abs(b[1] - wy) + 0.5, z_in - z0 - reach]);
    }
}

// Inner wall between the BME280 and the warm inside, with a notch for its wires.
module partition() difference() {
    translate([part_x - 0.6, y0 - 0.01, face - 0.01]) cube([1.2, in_h + 0.02, z_in - face + 0.01]);
    translate([part_x - 1, bme_y - 3, z_in - 4]) cube([2, 6, 5]);   // wire notch, level with the BME280's pins
}

// --- ESP32: a frame on the end wall around the board, open at the back
// (the USB end). Its front wall stands on the case's front wall; the long
// walls rise 1 mm past the board's face. Inside, the board's back rests on a
// block at its front end (no pins there) and two thin ledges along its edges,
// 1.5 mm off the end wall for the solder joints. Two lips on the long walls
// reach 0.7 over the board's front corners, 0.2 off its face: the board slides
// in from the back under them; the cover holds its USB end.
esp_zf  = esp_z1 - 23;              // board front edge (on the frame's front wall)
lip_w   = 0.7;                      // how far the lips reach over the board
lip_z   = 2.5;                      // and how far back from its front edge (the last pin pad starts at 2.8)
esp_fx  = esp_xb - 0.8 - 1.0;       // frame's inner edge: 1 mm past the board's face
module esp_mount() {
    fx = esp_fx;
    hw = 9 + esp_cl;                // half the inside width
    difference() {
        translate([fx, esp_yc - hw - fr_t, face - 0.01]) cube([xe - fx + 0.01, 2 * (hw + fr_t), esp_z1 + 0.2 - face]);
        translate([fx - 1, esp_yc - hw, esp_zf]) cube([xe - fx + 1, 2 * hw, z_in]);   // up to the end wall: 1.5 for the solder
    }
    translate([esp_xb, esp_yc - hw, esp_zf - 0.01]) cube([esp_off + 0.01, 2 * hw, 2.5]);                     // block
    for (s = [-1, 1]) translate([esp_xb, s < 0 ? esp_yc - hw - 0.01 : esp_yc + hw - 0.55, esp_zf]) cube([esp_off + 0.01, 0.56, 23]);   // ledges
    for (s = [-1, 1]) translate([fx - 0.01, s < 0 ? esp_yc - hw - 0.01 : esp_yc + 9 - lip_w, esp_zf - 0.01])
        cube([esp_xb - 0.8 - 0.2 - fx + 0.01, hw - 9 + lip_w + 0.01, lip_z + 0.01]);                              // lips
}
// The cover prints outside down, so the plug recess is on the bed; the step
// from it to the socket hole is a 45 degree slope, not a flat ledge (a flat
// one printed in the air and came out stringy).
module usb_hole() {
    translate([usb_xc - 1.85, usb_yc - 4.7, z_in - 0.1]) cube([3.7, 9.4, cover_t + 0.2]);
    translate([usb_xc - 3.5, usb_yc - 6.4, z_in + 1.5]) cube([7.0, 12.8, cover_t]);                       // plug recess
    hull() {
        translate([usb_xc - 3.5, usb_yc - 6.4, z_in + 1.5]) cube([7.0, 12.8, 0.01]);
        translate([usb_xc - 1.85, usb_yc - 4.7, z_in + 1.5 - 1.7]) cube([3.7, 9.4, 0.01]);
    }
}

// --- light sensor: on two posts behind the front, M3 screws from the back;
// a tube around the chip keeps the light inside the case away from it.
function ls_holes() = [for (s = [-1, 1]) [ls_x + s * 4.5, ls_y + 18.5 / 2 - 2.4]];   // [x, y]
module ls_mounts() {
    // posts cut flat on the right where the strap used to be,
    intersection() {
        union() for (p = ls_holes()) translate([p[0], p[1], face - 0.01]) cylinder(d = 6, h = ls_post + 0.01);
        // and on the display side 0.3 clear of the display's end (they touched it)
        translate([xd + 0.3, -10, -1]) cube([esp_xb - 4.4 - xd - 0.3, 100, 50]);
    }
    translate([ls_x, ls_y + ls_chip, face - 0.01])
        difference() { cylinder(d = 7, h = ls_post - 0.3 + 0.01); translate([0, 0, -0.1]) cylinder(d = 4.6, h = ls_post + 1); }
}
module ls_window() translate([ls_x, ls_y + ls_chip, -0.01]) cylinder(d1 = 4.5, d2 = 3, h = face + 0.02);   // wider outside

// --- BME280
module bme_frame() {
    hw = bme_w / 2 + esp_cl;
    fx = bme_xb + 1.0;              // frame walls stand 1 mm past the board's back
    z0 = bme_zf - fr_t;             // the frame's floor (towards the front)
    difference() {
        union() {
            translate([-xe - 0.01, bme_y - hw - fr_t, z0]) cube([fx + xe + 0.01, 2 * (hw + fr_t), bme_top - z0 + 0.01]);
            // under the floor, 45 degrees back to the end wall, so it prints without support
            hull() {
                translate([-xe - 0.01, bme_y - hw - fr_t, z0]) cube([fx + xe + 0.01, 2 * (hw + fr_t), 0.01]);
                translate([-xe - 0.01, bme_y - hw - fr_t, z0 - (fx + xe)]) cube([0.01, 2 * (hw + fr_t), 0.01]);
            }
        }
        translate([-xe - 1, bme_y - hw, bme_zf]) cube([fx + xe + 2, 2 * hw, 50]);
    }
    for (s = [-1, 1]) translate([-xe - 0.01, s < 0 ? bme_y - hw - 0.01 : bme_y + hw - 0.41, bme_zf]) cube([bme_gap + 0.01, 0.42, bme_top - bme_zf]);   // ledges
    // lips over the board's inner face, so it slides in like a drawer
    for (s = [-1, 1]) translate([bme_xb + 0.2, s < 0 ? bme_y - hw - 0.01 : bme_y + hw - 0.61, bme_zf - 0.01]) cube([fx - bme_xb - 0.2 + 0.01, 0.62, bme_top - bme_zf + 0.01]);
}
// slots in the end wall in front of the sensor (they run front to back, so
// they print as plain vertical slits)
module bme_vents() for (i = [-2:2])
    translate([-xe - wall - 0.1, bme_y + i * 2.4 - 0.6, bme_zf + 0.8]) cube([wall + 0.2, 1.2, bme_l - 1.6]);
// two fingers on the cover hold the board's back edge, either side of the pins
module bme_fingers() for (s = [-1, 1])
    translate([bme_xp, bme_y + s * (bme_w / 2 - 0.6) - 0.6, bme_zf + bme_l]) cube([1.5, 1.2, z_in - bme_zf - bme_l + 0.01]);

// ================================================================ the stand
// A plate on the desk under the whole length, and a wedge between it and the
// case's underside. Made in the desk frame, then turned into the case frame.
desk = -(out_d * sin(tilt));           // plate top: where the cover's lower back edge is
module stand_desk() {
    translate([-out_len / 2, desk - base_t, -2]) cube([out_len, base_t, base_d + 2]);
    intersection() {
        rotate([tilt, 0, 0]) translate([-out_len / 2, -8, 0]) cube([out_len, 8.01, z_in]);
        translate([-out_len / 2, desk - 0.5, -5]) cube([out_len, 10, base_d + 5]);
    }
}
module stand() intersection() {
    rotate([-tilt, 0, 0]) stand_desk();
    translate([-out_len, -50, 0]) cube([2 * out_len, 100, 200]);   // nothing in front of the face
}

// =============================================================== the cover
module cover(side) {
    s = side == "r" ? 1 : -1;
    x0 = side == "r" ? 0 : -out_len / 2;
    x1 = side == "r" ? out_len / 2 : 0;
    difference() {
        union() {
            translate([x0, 0, z_in]) cube([x1 - x0, out_h, cover_t]);
            // lip inside the walls, to line it up
            difference() {
                intersection() {
                    translate([x0, 0, z_in - 2]) cube([x1 - x0, out_h, 2.01]);
                    difference() {
                        translate([-xe + 0.2, y0 + 0.2, z_in - 2]) cube([in_len - 0.4, in_h - 0.4, 2.01]);
                        translate([-xe + 1.4, y0 + 1.4, z_in - 3]) cube([in_len - 2.8, in_h - 2.8, 4]);
                    }
                }
                if (!one_piece) translate([-8, -1, z_in - 3]) cube([16, out_h + 2, 4]);   // the tongue
                for (b = bosses) translate([b[0] - boss_d / 2 - 0.5, -1, z_in - 3]) cube([boss_d + 1, out_h + 2, 4]);
                                translate([esp_xb - 3, esp_yc - 12, z_in - 3]) cube([6, 24, 4]);                  // ESP32 frame
                translate([part_x - 1.2, y0 - 1, z_in - 3]) cube([2.4, in_h + 2, 4]);        // partition
                translate([-xe - 1, bme_y - bme_w / 2 - 3, z_in - 3]) cube([bme_xb + 2 + xe, bme_w + 6, 4]);  // BME280 frame
            }
            // ribs that keep the boards against the front
            for (y = [y0 + 3, y1 - 3], r = side == "r" ? [[green_x + 12, xd - 7]] : [[-(xd - 7), -green_x - 12]])
                translate([r[0], y - 0.8, z_pback + 0.1]) cube([r[1] - r[0], 1.6, z_in - z_pback - 0.1 + 0.01]);
            if (side == "l") bme_fingers();
            for (m = mids) if (m[0] * s > 0) mid_tab(m);
        }
        for (b = bosses) if (b[0] * s > 0) translate([b[0], b[1], z_in - 1]) cylinder(d = free_d, h = 10);
        if (side == "r") usb_hole();
        for (m = mids) if (m[0] * s > 0) mid_insert(m);
        // vents over the BME280 room
        if (side == "l") for (i = [-3:3]) translate([-xe + 1, bme_y + i * 3 - 0.6, z_in - 1]) cube([part_x - 0.6 - 1 + xe - 1, 1.2, 5]);
    }
    if (side == "r") usb_wall();
}
// A wall from the cover down beside the USB socket's top: with the end wall
// it holds the board's USB end when a plug goes in or out. About half the
// socket's length, 0.15 off its face; it grows up from the cover as printed.
usb_wall_h = 3.5;
module usb_wall() {
    sx = esp_xb - 0.8 - 3.1;          // the socket's top face
    // 2 mm thick, and a 45 degree buttress behind it, so it can't snap off
    hull() {
        translate([sx - 0.15 - 2, usb_yc - 5, z_in - usb_wall_h]) cube([2, 10, usb_wall_h + 0.01]);
        translate([sx - 0.15 - 2 - usb_wall_h, usb_yc - 5, z_in]) cube([usb_wall_h + 2, 10, 0.01]);
    }
}
// partbin's board (parts up, USB towards +y) turned so its parts face the
// inside (-x), the USB points back (+z) and its underside rests at esp_xb.
module esp_place() translate([esp_xb, esp_yc, esp_z1 - 11.5])
    multmatrix([[0, 0, -1, 0], [-1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]]) children();

// ================================================================ halves
module half(side) {
    intersection() {
        union() { box(); if (with_stand) stand(); }
        translate(side == "r" ? [0, -50, -1] : [-out_len, -50, -1]) cube([out_len, 150, 200]);
    }
    if (side == "r") tongue();
}
// On the right half, reaching 6 mm into the left one along the top and bottom
// walls behind the boards (glue it in).
// It runs 6 mm along the right half's own wall too, so it's properly joined,
// and the part that sticks out past the seam has a 45 degree underside.
module tongue() {
    z0 = z_pback + green + 0.4;
    z1 = z_in - 0.2;
    for (y = [y0 - 0.01, y1 - 1.2]) hull() {
        translate([0, y, z0]) cube([6, 1.21, z1 - z0]);
        translate([-6, y, z0 + 6]) cube([6.01, 1.21, z1 - z0 - 6]);
    }
}

// ============================================================ dummy parts
// The display: 8 blocks on two blue boards, and the green strips behind the joint.
preview_cols = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 127, 65, 65, 65, 62, 0, 56, 68, 68, 56, 0, 4, 127, 4, 0, 127, 2, 12, 2, 127, 0, 56, 68, 68, 124, 0, 4, 127, 4, 0, 124, 4, 4, 8, 0, 125, 0, 108, 16, 16, 108, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
lit = false;   // pictures: light the LEDs in preview_cols

module boards() translate([0, y0 + fit, 0]) {
    for (k = [0:7]) translate([-disp_len / 2 + k * (block + gap), 0, z_led]) {
        color([0.12, 0.12, 0.12]) cube([block, disp_h, 0.4]);
        color([0.92, 0.9, 0.84]) translate([0, 0, 0.4]) cube([block, disp_h, led - 0.4 - 3]);
        color([0.15, 0.15, 0.15]) translate([1, 2, led - 3]) cube([block - 2, disp_h - 4, 3]);    // sockets
        for (i = [0:7], j = [0:7])
            color(lit && floor(preview_cols[k * 8 + i] / pow(2, 7 - j)) % 2 == 1 ? [0.2, 1, 0.35] : lit ? [0.2, 0.24, 0.2] : [0.85, 0.85, 0.8]) translate([block / 16 + i * block / 8, disp_h / 16 + j * disp_h / 8, -0.01]) cylinder(d = 3, h = 0.05, $fn = 12);
    }
    for (s = [-1, 1]) color([0.1, 0.25, 0.6]) translate([s > 0 ? gap / 2 : -disp_len / 2, 0, z_pcb]) cube([disp_len / 2 - gap / 2, disp_h, pcb]);
    for (y = [0, disp_h - green_y]) color([0.1, 0.55, 0.3]) translate([-green_x, y, z_pback]) cube([2 * green_x, green_y, green]);
}
module esp() esp_place() esp32c3_supermini(detail = false);
module light() translate([ls_x, ls_y, face + ls_post + 1.6]) rotate([0, 180, 0]) gy302_bh1750(detail = false);
// partbin's board (parts up, pins towards -y) turned so its parts face the end
// wall (-x), its pins point back (+z) and it spans y.
module bme() translate([bme_xb, bme_y, bme_zf + bme_l / 2])
    multmatrix([[0, 0, -1, 0], [1, 0, 0, 0], [0, -1, 0, 0], [0, 0, 0, 1]])
        scale([bme_w / 15, bme_l / 10.2, 1.5 / 1.6]) gy_bme280(detail = false);   // partbin's typical board, stretched to the measured size
module inside() { boards(); esp(); light(); bme(); }

c_case = [0.16, 0.16, 0.18];
c_cover = [0.28, 0.28, 0.3];

module assembled(open = false) {
    d = open ? 30 : 0;
    translate([-d, 0, 0]) color(c_case) half("l");
    translate([d, 0, 0]) color(c_case) half("r");
    translate([-d, 0, open ? 40 : 0]) color(c_cover) cover("l");
    translate([d, 0, open ? 40 : 0]) color(c_cover) cover("r");
    if (!open) inside();
    else { translate([d, 0, 0]) esp(); translate([d, 0, 0]) light(); translate([-d, 0, 0]) bme(); }
}

// Shown on the desk: turned so the desk is the x-y plane (z up).
module on_desk() rotate([90, 0, 0]) translate([0, -desk + base_t, 0]) rotate([tilt, 0, 0]) children();

// Standing as on the shelf: y up stays up, the front faces -y (towards the camera at -y).
module upright() rotate([90, 0, 0]) mirror([0, 0, 1]) children();

module case_whole() { box(); if (with_stand) stand(); }
module cover_whole() union() { cover("l"); cover("r"); }

module whole(open = false) {
    color(c_case) case_whole();
    translate([0, 0, open ? 70 : 0]) color(c_cover) cover_whole();
    inside();
}

// test pieces
module test_box() translate([xd + 0.2, -0.01, -0.01]) cube([out_len / 2 - xd, out_h + 0.02, out_d]);
module test_box_l() translate([-out_len / 2 - 0.01, -0.01, -0.01]) cube([out_len / 2 - xd - 0.2 + 0.01, out_h + 0.02, out_d]);
module flip() translate([0, 0, out_d]) rotate([180, 0, 0]) children();

if (part == "case") case_whole();
if (part == "cover") flip() cover_whole();
if (part == "test_frame") intersection() { case_whole(); translate([-out_len, -1, -0.01]) cube([2 * out_len, out_h + 2, 2.01]); }
if (part == "test_end") intersection() { case_whole(); test_box(); }
if (part == "test_cover") flip() intersection() { cover_whole(); test_box(); }
if (part == "test_end_l") intersection() { case_whole(); test_box_l(); }
if (part == "test_cover_l") flip() intersection() { cover_whole(); test_box_l(); }
if (part == "all") upright() whole();
if (part == "open") upright() whole(true);
if (part == "section") upright() intersection() { whole(); translate([xd - 8, -1, -1]) cube([40, esp_yc + 1, 60]); }
