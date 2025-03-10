from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING, Literal

import pytest
import torch
from ase.filters import ExpCellFilter, Filter, FrechetCellFilter
from pytest import approx, mark, param

from chgnet.graph import CrystalGraphConverter
from chgnet.model import CHGNet, StructOptimizer

if TYPE_CHECKING:
    from pymatgen.core import Structure


@pytest.mark.parametrize(
    "algorithm, ase_filter", [("legacy", FrechetCellFilter), ("fast", ExpCellFilter)]
)
def test_relaxation(
    algorithm: Literal["legacy", "fast"], ase_filter: Filter, li_mn_o2: Structure
) -> None:
    chgnet = CHGNet.load()
    converter = CrystalGraphConverter(
        atom_graph_cutoff=6, bond_graph_cutoff=3, algorithm=algorithm
    )
    assert converter.algorithm == algorithm

    chgnet.graph_converter = converter
    relaxer = StructOptimizer(model=chgnet)
    result = relaxer.relax(li_mn_o2, verbose=True, ase_filter=ase_filter)
    assert list(result) == ["final_structure", "trajectory"]

    traj = result["trajectory"]
    # make sure trajectory has expected attributes
    assert {*traj.__dict__} == {
        *"atoms energies forces stresses magmoms atom_positions cells".split()
    }
    assert len(traj) == 2 if algorithm == "legacy" else 4

    # make sure final structure is more relaxed than initial one
    assert traj.energies[-1] == approx(-58.94209, rel=1e-4)


no_cuda = mark.skipif(not torch.cuda.is_available(), reason="No CUDA device")
# skip in macos-14 M1 CI due to OOM error (TODO investigate if
# PYTORCH_MPS_HIGH_WATERMARK_RATIO can fix)
no_mps = mark.skipif(
    not torch.backends.mps.is_available() or "CI" in os.environ, reason="No MPS device"
)


@mark.parametrize(
    "use_device", ["cpu", param("cuda", marks=no_cuda), param("mps", marks=no_mps)]
)
def test_structure_optimizer_passes_kwargs_to_model(use_device: str) -> None:
    relaxer = StructOptimizer(use_device=use_device)
    assert re.match(rf"{use_device}(:\d+)?", relaxer.calculator.device)
