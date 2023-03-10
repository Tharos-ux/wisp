build:
  @python -m pip install . --quiet

env:
  @WD=$(pwd)
  @export CONDA_ALWAYS_YES="true"
  @conda create -p $WD"/.env" python=3.10
  @conda activate $WD"/.env"
  @python setup.py install
  @unset CONDA_ALWAYS_YES
  @conda deactivate