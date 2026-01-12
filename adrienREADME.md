### FROM ADRIEN:
## Adrien workspace (safe sandbox)
This folder contains Adrien's experimental work based on Miles Couchman's `INCITE` repo.
Goal:
- keep Miles' original files in the repo root untouched
- do all edits and experiments inside `adrien/`
- sync my work to *my fork* on GitHub without affecting Miles' repo
- optionally propose changes back to Miles via Pull Requests

## Safety model (what protects Miles's repo)
This clone has two remotes:
- `origin`   = Adrien's fork (safe to push)
- `upstream` = Miles' repo (push disabled in this setup)

Check anytime:
git remote -v

## How to push my local changes to the repo
Run these from inside the repo directory.

# 1. Make sure you’re on the right branch
    git branch
If needed:
    git checkout adrien

# 2. Check what changed
    git status

# 3. Stage files
Everything:
    git add .
Or specific files:
    git add path/to/file

# 4. Commit
    git commit -m "Short, clear description of the change"
(If this says “nothing to commit”, you’re already clean.)

# 5. Push to GitHub
    git push origin adrien

Very quick mental model
	•	edit files
	•	git status
	•	git add
	•	git commit
	•	git push
That’s all I need 95% of the time.

### FROM MILES:
## Setting up Jupyter notebook on Andes, showing on your local computer

- Instructions for how to setup conda environment [here](https://docs.olcf.ornl.gov/software/python/conda_basics.html)

**In terminal:**
```
ssh username@andes.olcf.ornl.gov
salloc -A cfd135 -N 1 -t 01:00:00  #Interactive node for an hour
module load python
source activate andes1 #To activate conda environment, need to set this up for yourself
jupyter-lab --no-browser --ip=0.0.0.0 --port=8095
```

**On local computer:**
```
ssh -L localhost:8095:andes##:8095 -fN mcouchman@andes-login%%.olcf.ornl.gov # replace ## with allocated andes node, %% with login node
http://localhost:8095 #in local browser
```

## Description of files:

- **paramClassSheared.py:** Generates a Python class for each simulation containing the relevant parameters and other useful information (directory path, etc.)
- **visualizeData.ipynb:** Jupyter notebook with sample code to visualize slices of data, compute chi etc.
