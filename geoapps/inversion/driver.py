#  Copyright (c) 2022 Mira Geoscience Ltd.
#
#  This file is part of geoapps.
#
#  geoapps is distributed under the terms and conditions of the MIT License
#  (see LICENSE file at the root of this source code package).

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geoapps.inversion import InversionBaseParams

import multiprocessing
import sys
from multiprocessing.pool import ThreadPool
from time import time
from uuid import UUID

import numpy as np
from dask import config as dconf
from dask.distributed import Client, LocalCluster, get_client
from geoh5py.ui_json import InputFile
from SimPEG import inverse_problem, inversion, maps, optimization, regularization
from SimPEG.utils import tile_locations

from geoapps.inversion.components import (
    InversionData,
    InversionMesh,
    InversionModelCollection,
    InversionTopography,
    InversionWindow,
)
from geoapps.inversion.components.factories import DirectivesFactory, MisfitFactory
from geoapps.inversion.params import InversionBaseParams


class InversionDriver:
    def __init__(self, params: InversionBaseParams, warmstart=True):
        self.params = params
        self.warmstart = warmstart
        self.workspace = params.geoh5
        self.inversion_type = params.inversion_type
        self.inversion_window = None
        self.inversion_data = None
        self.inversion_topography = None
        self.inversion_mesh = None
        self.inversion_models = None
        self.inverse_problem = None
        self.survey = None
        self.active_cells = None
        self.initialize()

    @property
    def window(self):
        return self.inversion_window.window

    @property
    def data(self):
        return self.inversion_data.observed

    @property
    def locations(self):
        return self.inversion_data.locations

    @property
    def topography(self):
        return self.inversion_topography.topography

    @property
    def mesh(self):
        return self.inversion_mesh.mesh

    @property
    def starting_model(self):
        return self.models.starting

    @property
    def reference_model(self):
        return self.models.reference

    @property
    def lower_bound(self):
        return self.models.lower_bound

    @property
    def upper_bound(self):
        return self.models.upper_bound

    def initialize(self):

        ### Collect inversion components ###

        self.configure_dask()

        self.inversion_window = InversionWindow(self.workspace, self.params)

        self.inversion_data = InversionData(self.workspace, self.params, self.window)

        self.inversion_topography = InversionTopography(
            self.workspace, self.params, self.window
        )

        self.inversion_mesh = InversionMesh(
            self.workspace, self.params, self.inversion_data, self.inversion_topography
        )

        self.models = InversionModelCollection(
            self.workspace, self.params, self.inversion_mesh
        )

        # TODO Need to setup/test workers with address
        if self.params.distributed_workers is not None:
            try:
                get_client()
            except ValueError:
                cluster = LocalCluster(processes=False)
                Client(cluster)

        # Build active cells array and reduce models active set
        self.active_cells = self.inversion_topography.active_cells(
            self.inversion_mesh, self.inversion_data
        )
        self.workspace.remove_entity(self.inversion_topography.entity)
        self.models.edit_ndv_model(
            self.inversion_mesh.entity.get_data("active_cells")[0].values.astype(bool)
        )
        self.models.remove_air(self.active_cells)
        self.active_cells_map = maps.InjectActiveCells(
            self.mesh, self.active_cells, np.nan
        )
        self.n_cells = int(np.sum(self.active_cells))
        self.is_vector = self.models.is_vector
        self.n_blocks = 3 if self.is_vector else 1
        self.is_rotated = False if self.inversion_mesh.rotation is None else True

        # Create SimPEG Survey object
        self.survey = self.inversion_data._survey

        # Tile locations
        self.tiles = self.get_tiles()  # [np.arange(len(self.survey.source_list))]#

        self.n_tiles = len(self.tiles)
        print(f"Setting up {self.n_tiles} tile(s) ...")
        # Build tiled misfits and combine to form global misfit

        self.global_misfit, self.sorting = MisfitFactory(
            self.params, models=self.models
        ).build(self.tiles, self.inversion_data, self.mesh, self.active_cells)
        print(f"Done.")

        # Create regularization
        self.regularization = self.get_regularization()

        # Specify optimization algorithm and set parameters
        self.optimization = optimization.ProjectedGNCG(
            maxIter=self.params.max_iterations,
            lower=self.lower_bound,
            upper=self.upper_bound,
            maxIterLS=self.params.max_line_search_iterations,
            maxIterCG=self.params.max_cg_iterations,
            tolCG=self.params.tol_cg,
            stepOffBoundsFact=1e-8,
            LSshorten=0.25,
        )

        # Create the default L2 inverse problem from the above objects
        self.inverse_problem = inverse_problem.BaseInvProblem(
            self.global_misfit,
            self.regularization,
            self.optimization,
            beta=self.params.initial_beta,
        )

        # Solve forward problem, and attach dpred to inverse problem or
        if self.params.forward_only:
            print("Running forward simulation ...")
        else:
            print("Pre-computing sensitivities ...")

        if self.warmstart or self.params.forward_only:
            self.inverse_problem.dpred = self.inversion_data.simulate(
                self.starting_model, self.inverse_problem, self.sorting
            )

        # If forward only option enabled, stop here
        if self.params.forward_only:
            return

        # Add a list of directives to the inversion
        self.directiveList = DirectivesFactory(self.params).build(
            self.inversion_data,
            self.inversion_mesh,
            self.active_cells,
            np.argsort(np.hstack(self.sorting)),
            self.global_misfit,
            self.regularization,
        )

        # Put all the parts together
        self.inversion = inversion.BaseInversion(
            self.inverse_problem, directiveList=self.directiveList
        )

    def run(self):
        """Run inversion from params"""

        if self.params.forward_only:
            print("Running the forward simulation ...")
            self.inversion_data.simulate(
                self.starting_model, self.inverse_problem, self.sorting
            )
            return

        # Run the inversion
        self.start_inversion_message()
        mrec = self.inversion.run(self.starting_model)

    def start_inversion_message(self):

        # SimPEG reports half phi_d, so we scale to match
        has_chi_start = self.params.starting_chi_factor is not None
        chi_start = (
            self.params.starting_chi_factor if has_chi_start else self.params.chi_factor
        )
        print(f"Starting {self.params.inversion_style} inversion...")
        print(
            "Target Misfit: {:.2e} ({} data with chifact = {}) / 2".format(
                0.5 * self.params.chi_factor * len(self.survey.std),
                len(self.survey.std),
                self.params.chi_factor,
            )
        )
        print(
            "IRLS Start Misfit: {:.2e} ({} data with chifact = {}) / 2".format(
                0.5 * chi_start * len(self.survey.std), len(self.survey.std), chi_start
            )
        )

    def get_regularization(self):

        if self.inversion_type == "magnetic vector":
            wires = maps.Wires(
                ("p", self.n_cells), ("s", self.n_cells), ("t", self.n_cells)
            )

            reg_p = regularization.Sparse(
                self.mesh,
                indActive=self.active_cells,
                mapping=wires.p,
                gradientType=self.params.gradient_type,
                alpha_s=self.params.alpha_s,
                alpha_x=self.params.alpha_x,
                alpha_y=self.params.alpha_y,
                alpha_z=self.params.alpha_z,
                norms=self.params.model_norms(),
                mref=self.reference_model,
            )
            reg_s = regularization.Sparse(
                self.mesh,
                indActive=self.active_cells,
                mapping=wires.s,
                gradientType=self.params.gradient_type,
                alpha_s=self.params.alpha_s,
                alpha_x=self.params.alpha_x,
                alpha_y=self.params.alpha_y,
                alpha_z=self.params.alpha_z,
                norms=self.params.model_norms(),
                mref=self.reference_model,
            )

            reg_t = regularization.Sparse(
                self.mesh,
                indActive=self.active_cells,
                mapping=wires.t,
                gradientType=self.params.gradient_type,
                alpha_s=self.params.alpha_s,
                alpha_x=self.params.alpha_x,
                alpha_y=self.params.alpha_y,
                alpha_z=self.params.alpha_z,
                norms=self.params.model_norms(),
                mref=self.reference_model,
            )

            # Assemble the 3-component regularizations
            reg = reg_p + reg_s + reg_t
            reg.mref = self.reference_model

        else:

            reg = regularization.Sparse(
                self.mesh,
                indActive=self.active_cells,
                mapping=maps.IdentityMap(nP=self.n_cells),
                gradientType=self.params.gradient_type,
                alpha_s=self.params.alpha_s,
                alpha_x=self.params.alpha_x,
                alpha_y=self.params.alpha_y,
                alpha_z=self.params.alpha_z,
                norms=self.params.model_norms(),
                mref=self.reference_model,
            )

        return reg

    def get_tiles(self):

        if self.params.inversion_type in ["direct current", "induced polarization"]:
            tiles = []
            potential_electrodes = self.inversion_data.entity
            current_electrodes = potential_electrodes.current_electrodes
            line_split = np.array_split(
                current_electrodes.unique_parts, self.params.tile_spatial
            )
            for split in line_split:
                split_ind = []
                for line in split:
                    electrode_ind = current_electrodes.parts == line
                    cells_ind = np.where(
                        np.any(electrode_ind[current_electrodes.cells], axis=1)
                    )[0]
                    split_ind.append(cells_ind)
                # Fetch all receivers attached to the currents
                logical = np.zeros(current_electrodes.n_cells, dtype="bool")
                if len(split_ind) > 0:
                    logical[np.hstack(split_ind)] = True
                    tiles.append(
                        np.where(logical[potential_electrodes.ab_cell_id.values - 1])[0]
                    )

            # TODO Figure out how to handle a tile_spatial object to replace above

        else:
            tiles = tile_locations(
                self.locations,
                self.params.tile_spatial,
                method="kmeans",
            )

        return tiles

    def fetch(self, p: str | UUID):
        """Fetch the object addressed by uuid from the workspace."""

        if isinstance(p, str):
            try:
                p = UUID(p)
            except:
                p = self.params.__getattribute__(p)

        try:
            return self.workspace.get_entity(p)[0].values
        except AttributeError:
            return self.workspace.get_entity(p)[0]

    def configure_dask(self):
        """Sets Dask config settings."""

        if self.params.parallelized:
            if self.params.n_cpu is None:
                self.params.n_cpu = int(multiprocessing.cpu_count() / 2)

            dconf.set({"array.chunk-size": str(self.params.max_chunk_size) + "MiB"})
            dconf.set(scheduler="threads", pool=ThreadPool(self.params.n_cpu))


def start_inversion(filepath=None, **kwargs):
    """Starts inversion with parameters defined in input file."""

    if filepath is not None:
        input_file = InputFile.read_ui_json(filepath)
        inversion_type = input_file.data.get("inversion_type")
    else:
        input_file = None
        inversion_type = kwargs.get("inversion_type")

    if inversion_type == "magnetic vector":
        from .potential_fields import MagneticVectorParams as ParamClass
        from .potential_fields.magnetic_vector.constants import validations

    elif inversion_type == "magnetic scalar":
        from .potential_fields import MagneticScalarParams as ParamClass
        from .potential_fields.magnetic_scalar.constants import validations

    elif inversion_type == "gravity":
        from .potential_fields import GravityParams as ParamClass
        from .potential_fields.gravity.constants import validations

    elif inversion_type == "magnetotellurics":
        from .natural_sources import MagnetotelluricsParams as ParamClass
        from .natural_sources.magnetotellurics.constants import validations

    elif inversion_type == "tipper":
        from .natural_sources import TipperParams as ParamClass
        from .natural_sources.tipper.constants import validations

    elif inversion_type == "direct current":
        from .electricals import DirectCurrentParams as ParamClass
        from .electricals.direct_current.constants import validations

    elif inversion_type == "induced polarization":
        from .electricals import InducedPolarizationParams as ParamClass
        from .electricals.induced_polarization.constants import validations

    else:
        raise UserWarning("A supported 'inversion_type' must be provided.")

    input_file = InputFile.read_ui_json(filepath, validations=validations)
    params = ParamClass(input_file=input_file, **kwargs)
    driver = InversionDriver(params)
    driver.run()


if __name__ == "__main__":
    ct = time()
    filepath = sys.argv[1]
    start_inversion(filepath)
    print(f"Total runtime: {datetime.timedelta(seconds=time() - ct)}")