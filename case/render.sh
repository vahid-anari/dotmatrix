#!/bin/sh
# Export the STL files and preview pictures:  ./render.sh   (needs OpenSCAD)
cd "$(dirname "$0")"
mkdir -p stl images
for p in shell back foot; do
  openscad -q -D "part=\"$p\"" -o "stl/$p.stl" dotmatrix_case.scad
done
shot() { xvfb-run -a openscad -q --imgsize=1600,900 --colorscheme=Tomorrow --projection=p \
          --camera="$2" -D "part=\"$3\"" -o "images/$1.png" dotmatrix_case.scad; }
# camera: eye x,y,z, then the point it looks at (x along the case, y towards the back, z up)
shot front    -200,-470,190,0,20,20  all
shot back     -200,520,190,0,20,20   all
shot side     420,18,24,0,18,24      all
shot section  40,-30,90,140,20,15    section
