#!/bin/bash
#SBATCH --job-name=bsee_sif_ultra_peft
#SBATCH --account=bsee_safety_ai
#SBATCH --partition=gpu_partition
#SBATCH --nodes=4
#SBATCH --gpus-per-node=4          # GB200: 4 GPUs/node -> 16 GPUs total
#SBATCH --segment=4
#SBATCH --time=12:00:00
#SBATCH --output=bsee_ultra_peft_%j.log

set -uo pipefail

# --- Credentials ---
export HF_TOKEN="your-hf-token"
export HF_HOME=/shared/hf_cache
export WANDB_API_KEY="your-wandb-key"

export CONT=nvcr.io/nvidia/nemo-automodel:26.04.00
export CONT_NAME=nemo-automodel-2604

# --- Mounts: overlay Automodel on /opt/Automodel, and BSEE data on /data ---
export CONT_MOUNT="\
/shared/Automodel:/opt/Automodel,\
/shared/hf_cache:/shared/hf_cache,\
/shared/SIIH2026/data:/data"

GPUS_PER_NODE=4
CONFIG=/opt/Automodel/examples/llm_finetune/nemotron/nemotron_ultra_v3_bsee_peft.yaml

HEAD=$(scontrol show hostnames "$SLURM_JOB_NODELIST" | head -n1)
echo "==> job $SLURM_JOB_ID on $SLURM_JOB_NODELIST | head=$HEAD | config=$CONFIG"

srun \
    --container-image="$CONT" \
    --container-name="$CONT_NAME" \
    --container-mounts="$CONT_MOUNT" \
    --no-container-mount-home \
    --export=ALL,HF_TOKEN="$HF_TOKEN",HF_HOME="$HF_HOME",WANDB_API_KEY="$WANDB_API_KEY" \
    -N "$SLURM_NNODES" --ntasks-per-node=1 \
    bash -c 'cd /opt/Automodel && torchrun \
        --nnodes='"$SLURM_NNODES"' --nproc-per-node='"$GPUS_PER_NODE"' --node-rank=$SLURM_NODEID \
        --rdzv-id=$SLURM_JOB_ID --rdzv-backend=c10d \
        --rdzv-endpoint='"$HEAD"':29500 \
        /opt/Automodel/examples/llm_finetune/finetune.py \
        --config '"$CONFIG"
