#  Copyright (c) 2022 Mira Geoscience Ltd.
#
#  This file is part of geoapps.
#
#  geoapps is distributed under the terms and conditions of the MIT License
#  (see LICENSE file at the root of this source code package).

# pylint: disable=W0613
# pylint: disable=W0221

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geoapps.driver_base.params import BaseParams

import numpy as np

from .simpeg_factory import SimPEGFactory


class ReceiversFactory(SimPEGFactory):
    """Build SimPEG receivers objects based on factory type."""

    def __init__(self, params: BaseParams):
        """
        :param params: Params object containing SimPEG object parameters.

        """
        super().__init__(params)
        self.simpeg_object = self.concrete_object()

    def concrete_object(self):

        if self.factory_type in ["magnetic vector", "magnetic scalar"]:
            from SimPEG.potential_fields.magnetics import receivers

            return receivers.Point

        elif self.factory_type == "gravity":
            from SimPEG.potential_fields.gravity import receivers

            return receivers.Point

        elif self.factory_type == "direct current":
            from SimPEG.electromagnetics.static.resistivity import receivers

            return receivers.Dipole

        elif self.factory_type == "induced polarization":
            from SimPEG.electromagnetics.static.induced_polarization import receivers

            return receivers.Dipole

        elif self.factory_type == "magnetotellurics":
            from SimPEG.electromagnetics.natural_source import receivers

            return receivers.Point3DImpedance

        elif self.factory_type == "tipper":
            from SimPEG.electromagnetics.natural_source import receivers

            return receivers.Point3DTipper

    def assemble_arguments(
        self, locations=None, data=None, local_index=None, mesh=None, active_cells=None
    ):
        """Provides implementations to assemble arguments for receivers object."""

        args = []

        if self.factory_type in ["direct current", "induced polarization"]:
            args += self._dcip_arguments(
                locations=locations,
                local_index=local_index,
            )

        elif self.factory_type in ["magnetotellurics"]:
            args += self._magnetotellurics_arguments(
                locations=locations,
                local_index=local_index,
                mesh=mesh,
                active_cells=active_cells,
            )

        else:
            args.append(locations[local_index])

        return args

    def assemble_keyword_arguments(
        self, locations=None, data=None, local_index=None, mesh=None, active_cells=None
    ):
        """Provides implementations to assemble keyword arguments for receivers object."""
        kwargs = {}
        if self.factory_type in ["gravity", "magnetic scalar", "magnetic vector"]:
            kwargs["components"] = list(data)
        if self.factory_type in ["magnetotellurics", "tipper"]:
            kwargs["orientation"] = list(data.keys())[0].split("_")[0][1:]
            kwargs["component"] = list(data.keys())[0].split("_")[1]
        if self.factory_type in ["tipper"]:
            kwargs["orientation"] = kwargs["orientation"][::-1]

        return kwargs

    def build(
        self, locations=None, data=None, local_index=None, mesh=None, active_cells=None
    ):
        receivers = super().build(
            locations=locations,
            data=data,
            local_index=local_index,
            mesh=mesh,
            active_cells=active_cells,
        )

        if (
            self.factory_type in ["tipper"]
            and getattr(self.params.data_object, "base_stations", None) is not None
        ):
            stations = self.params.data_object.base_stations.vertices
            if stations is not None:
                if stations.shape[0] == 1:
                    stations = np.tile(stations.T, self.params.data_object.n_vertices).T

                receivers.reference_locations = stations

        return receivers

    def _dcip_arguments(self, locations=None, local_index=None):

        args = []
        local_index = np.vstack(local_index)
        locations_m = locations[local_index[:, 0], :]
        locations_n = locations[local_index[:, 1], :]
        args.append(locations_m)

        if np.all(locations_m == locations_n):
            if self.factory_type == "direct current":
                from SimPEG.electromagnetics.static.resistivity import receivers
            else:
                from SimPEG.electromagnetics.static.induced_polarization import (
                    receivers,
                )
            self.simpeg_object = receivers.Pole
        else:
            args.append(locations_n)

        return args

    def _magnetotellurics_arguments(
        self, locations=None, local_index=None, mesh=None, active_cells=None
    ):

        args = []
        locs = locations[local_index]

        args.append(locs)

        return args
