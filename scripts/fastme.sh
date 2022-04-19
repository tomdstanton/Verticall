#!/usr/bin/env bash

# This script takes one argument (a PHYLIP distance matrix) and does the following:
#  * Runs FastME with thorough settings.
#  * Sets any negative branch lengths to zero.
#  * Midpoint-roots the tree.

# Requirements:
#  * FastME (gite.lirmm.fr/atgc/FastME)
#  * R (r-project.org)
#  * ape (ape-package.ird.fr)
#  * phangorn (cran.r-project.org/package=phangorn)

# Output filenames will be the same as the input file, but with ".phylip"
# replaced with ".newick" and ".info".
phylip="$1"
name="${phylip/.phylip/}"
newick="$name".newick
info="$name".info

# Build the tree:
fastme --method B --nni B --spr -i "$phylip" -o temp.newick -I "$info"

# Remove negative branch lengths and mid-point root:
R -e 'library(ape); library(phangorn); tree <- read.tree("temp.newick"); tree$edge.length <- pmax(tree$edge.length, 0.0); tree <- midpoint(tree); write.tree(tree, "temp.newick")'
mv temp.newick "$newick"
