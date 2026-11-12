// A clip-on foot for the Dot Matrix case: it leans the case back so the LEDs
// face a little upward. Print two. The case is pushed down into it; ribs on
// the inside of the lips grip it, with no screws.
//
// Printed lying on its side, as exported: the profile on the bed, so the lips
// are built within the layers (stronger) and nothing overhangs.
//
// The profile is in the case's end view: x from the case's front (0) to its
// back, y up; the part is `width` long along the case.

lean    = 15;     // degrees the case leans back (10 works too)
width   = 20;     // along the case
depth   = 28.1;   // the case, front face to the back of the cover
fit     = 0.15;   // clearance each side of the case
rib     = 0.25;   // ribs stand this far in from the lips (0.1 grip each side)
t       = 3;      // floor thickness, and the lips' thickness is `w`
w       = 2;
lip_f   = 2.5;    // front lip height: below the LEDs (they start 3.25 up)
lip_b   = 10;     // back lip height, against the cover
behind  = 20;     // how far the foot reaches behind the case
chamfer = 0.6;    // lead-in on the lips' inner top edges

$fn = 24;

module lean() rotate(-lean) children();

module profile() {
    slab_y0 = -t;
    // the case's slot, a little wider than the case, cut out of everything
    difference() {
        union() {
            lean() translate([-fit - w, slab_y0]) square([depth + 2 * fit + 2 * w, t]);
            lean() translate([-fit - w, 0]) square([w, lip_f]);
            lean() translate([depth + fit, 0]) square([w, lip_b]);
            // solid down to a flat base on the shelf, reaching back
            hull() {
                lean() translate([-fit - w, slab_y0]) square([depth + 2 * fit + 2 * w, t]);
                translate([base_x0(), base_y0()]) square([depth + behind - base_x0(), t]);
            }
        }
        lean() translate([-fit, 0]) square([depth + 2 * fit, 100]);
        // lead-in chamfers
        lean() {
            translate([-fit, lip_f]) rotate(45) square(chamfer * 1.42, center = true);
            translate([depth + fit, lip_b]) rotate(45) square(chamfer * 1.42, center = true);
        }
    }
    // ribs on the lips' inner faces, running along the width
    lean() {
        for (y = [0.5, 1.4]) translate([-fit - 0.01, y]) square([rib + 0.01, 0.5]);
        for (y = [1.5, 4.5, 7.5]) translate([depth + fit - rib, y]) square([rib + 0.01, 0.8]);
    }
}

// The rotated floor's lowest corner sets where the base sits.
function rot(p) = [p[0] * cos(-lean) - p[1] * sin(-lean), p[0] * sin(-lean) + p[1] * cos(-lean)];
function base_y0() = min(rot([-fit - w, -t])[1], rot([depth + fit + w, -t])[1]);
function base_x0() = rot([-fit - w, -t])[0];

linear_extrude(width) profile();
