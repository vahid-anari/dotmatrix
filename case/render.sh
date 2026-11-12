#!/bin/sh
# Export the STL files and the pictures:  ./render.sh   (needs OpenSCAD, and the
# partbin submodule: git submodule update --init)
cd "$(dirname "$0")"
mkdir -p stl images
for p in case cover test_frame test_end test_cover test_end_l test_cover_l; do
  openscad -q -D "part=\"$p\"" -o "stl/$p.stl" dotmatrix_case.scad &
done
openscad -q -o stl/foot.stl dotmatrix_foot.scad &
wait
# The whole thing put together, only for looking at (not for printing)
openscad -q -D 'part="all"' -o stl/assembled-preview.stl dotmatrix_case.scad
shot() { xvfb-run -a openscad -q --imgsize=1600,900 --colorscheme=Tomorrow --projection=p \
          --camera="$2" -D "part=\"$3\"" -D lit=true -o "images/$1.png" dotmatrix_case.scad; }
# camera: eye x,y,z, then the point it looks at (x along the case, y towards the back, z up)
shot front    -150,-500,110,0,10,19    all
shot back     150,420,160,0,10,19      all
shot open     60,450,330,0,45,10       open
shot feet     -300,-330,140,-30,20,10    on_feet
shot section  142,13,110,142,13,0      section
