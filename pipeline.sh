#!/bin/sh
#SBATCH --job-name=wisp_pipeline
#SBATCH --output=LOG_wisp_job.log
. /local/env/envconda.sh

# $1 must be something like "subsampled","full","143genomes"

# create mandatory dirs if not exist
mkdir -p "genomes/unk_"$1
mkdir -p "genomes/train_"$1
mkdir -p "data"
mkdir -p "output/"$1

# use conda env
conda activate "/home/genouest/genscale/sdubois/wisp-env"

python wisp.py "wisp_params_"$1".json" -b -t 8

for FILE in "genomes/train_"$1/*
do
    mv "genomes/train_"$1"/"$(basename $FILE) "genomes/unk_small/"
    python wisp.py "wisp_params_"$1".json" -e $(basename $FILE)
    mv "genomes/unk_"$1"/"$(basename $FILE) "genomes/train_small/"
done

conda deactivate