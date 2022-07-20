#!/bin/sh
#SBATCH --job-name=wisp
#SBATCH --output=logs/wisp-%j.log
#SBATCH --mail-user=siegfried.dubois@inria.fr
#SBATCH --mail-type=END,FAIL

. /local/env/envconda.sh

# create mandatory dirs if not exist
mkdir -p genomes/unk
mkdir -p genomes/train
mkdir -p data
mkdir -p output
mkdir -m logs

# use conda env
WD = pwd
conda activate $WD"/wisp_env"

##########################
#                        #
#    ARGS YOU CAN USE    #
#                        #
##########################

# calling build
# wisp.py -b -t 8

# calling dl
# utilities.py

# calling prediction
# wisp.py -t 8

python $1

conda deactivate

# example use:
# sbatch --cpus-per-task=8 --mem=80G wisp.sh "/home/genouest/genscale/sdubois/wisp-env" "wisp.py parameters_files/megadb -b"
# sbatch wisp.sh "/home/genouest/genscale/sdubois/wisp-env" "utilities.py extract_genomes 3 /scratch/sdubois/refseq /scratch/sdubois/lb_minion/train_mega"