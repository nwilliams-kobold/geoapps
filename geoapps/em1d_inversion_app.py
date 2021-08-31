#  Copyright (c) 2021 Mira Geoscience Ltd.
#
#  This file is part of geoapps.
#
#  geoapps is distributed under the terms and conditions of the MIT License
#  (see LICENSE file at the root of this source code package).

import json
import multiprocessing
import os
import os.path as path

import ipywidgets as widgets
import matplotlib.pyplot as plt
import numpy as np
from geoh5py.groups import ContainerGroup
from geoh5py.objects import BlockModel, Curve, Grid2D, Octree, Points, Surface
from geoh5py.workspace import Workspace
from ipywidgets.widgets import (
    Button,
    Checkbox,
    Dropdown,
    FloatText,
    HBox,
    IntText,
    Label,
    Layout,
    Text,
    ToggleButton,
    VBox,
    Widget,
)

from geoapps.base import BaseApplication
from geoapps.drivers.magnetic_vector_inversion import MagneticVectorDriver
from geoapps.io.Gravity.params import GravityParams
from geoapps.io.MagneticScalar.params import MagneticScalarParams
from geoapps.io.MagneticVector.constants import app_initializer
from geoapps.io.MagneticVector.params import MagneticVectorParams
from geoapps.plotting import PlotSelection2D
from geoapps.selection import LineOptions, ObjectDataSelection, TopographyOptions
from geoapps.utils import geophysical_systems
from geoapps.utils.utils import find_value, string_2_list


def inversion_defaults():
    """
    Get defaults for gravity, magnetics and EM1D inversions
    """
    defaults = {
        "units": {
            "gravity": "g/cc",
            "magnetic vector": "SI",
            "magnetic scalar": "SI",
            "EM1D": "S/m",
        },
        "property": {
            "gravity": "density",
            "magnetic vector": "effective susceptibility",
            "magnetic scalar": "susceptibility",
            "EM1D": "conductivity",
        },
        "reference_value": {
            "gravity": 0.0,
            "magnetic vector": 0.0,
            "magnetic scalar": 0.0,
            "EM1D": 1e-3,
        },
        "starting_value": {
            "gravity": 1e-4,
            "magnetic vector": 1e-4,
            "magnetic scalar": 1e-4,
            "EM1D": 1e-3,
        },
    }

    return defaults


class InversionApp(PlotSelection2D):

    _param_class = MagneticVectorParams
    _select_multiple = True
    _add_groups = False
    _sensor = None
    _lines = None
    _topography = None
    inversion_parameters = None
    _spatial_options = None
    defaults = {}

    def __init__(self, ui_json=None, **kwargs):

        app_initializer.update(kwargs)
        if ui_json is not None and path.exists(ui_json):
            self.params = self._param_class.from_path(ui_json)
        else:
            if "h5file" in app_initializer.keys():
                app_initializer["geoh5"] = app_initializer.pop("h5file")
                app_initializer["workspace"] = app_initializer["geoh5"]

            self.params = self._param_class(**app_initializer)

        self.data_object = self.objects
        self.defaults.update(self.params.to_dict(ui_json_format=False))
        self.defaults.pop("workspace", None)
        self.em_system_specs = geophysical_systems.parameters()
        self._data_count = (Label("Data Count: 0"),)
        self._forward_only = Checkbox(
            value=False,
            description="Forward only",
        )
        self._inducing_field_strength = widgets.FloatText(
            description="Amplitude (nT)",
        )
        self._inducing_field_inclination = widgets.FloatText(
            description="Inclination (d.dd)",
        )
        self._inducing_field_declination = widgets.FloatText(
            description="Declination (d.dd)",
        )
        self._inversion_type = Dropdown(
            options=["magnetic vector", "magnetic scalar", "gravity"],
            description="Inversion Type:",
        )
        self._write = Button(
            value=False,
            description="Write input",
            button_style="warning",
            icon="check",
        )
        self.defaults.update(**kwargs)
        self._ga_group_name = widgets.Text(
            value="Inversion_", description="Save as:", disabled=False
        )
        self._chi_factor = FloatText(
            value=1, description="Target misfit", disabled=False
        )
        # self._uncert_mode = widgets.RadioButtons(
        #     options=[
        #         "Estimated (%|data| + background)",
        #         "User input (%|data| + floor)",
        #     ],
        #     value="User input (%|data| + floor)",
        #     disabled=False,
        # )
        # self._lower_bound = widgets.Text(
        #     value=None,
        #     description="Lower bound value",
        # )

        self._lower_bound_group = ModelOptions("lower_bound", **self.defaults)
        self._upper_bound_group = ModelOptions("upper_bound", **self.defaults)

        # self._upper_bound = widgets.Text(
        #     value=None,
        #     description="Upper bound value",
        # )
        self._ignore_values = widgets.Text(
            value="<0",
            description="Data (i.e. <0 = no negatives)",
        )
        self._max_iterations = IntText(value=10, description="Max beta Iterations")
        self._max_cg_iterations = IntText(value=30, description="Max CG Iterations")
        self._tol_cg = FloatText(value=1e-3, description="CG Tolerance")
        self._n_cpu = IntText(
            value=int(multiprocessing.cpu_count() / 2), description="Max CPUs"
        )
        self._max_ram = FloatText(value=2.0, description="Max RAM (Gb)")
        self._beta_start_options = widgets.RadioButtons(
            options=["value", "ratio"],
            value="ratio",
            description="Starting tradeoff (beta):",
        )
        self._beta_start = FloatText(value=1e2, description="phi_d/phi_m")
        self._beta_start_options.observe(self.initial_beta_change)
        self._beta_start_panel = HBox([self._beta_start_options, self._beta_start])
        self._optimization = VBox(
            [
                self._max_iterations,
                self._chi_factor,
                self._beta_start_panel,
                self._max_cg_iterations,
                self._tol_cg,
                self._n_cpu,
                self._max_ram,
            ]
        )
        self._starting_model_group = ModelOptions("starting_model", **self.defaults)
        self._starting_model_group.options.options = ["Constant", "Model"]
        # self._starting_model = self._starting_model_group.data
        # self._susceptibility_model = ModelOptions(
        #     units="SI", description="Background susceptibility", **kwargs
        # )
        # self._susceptibility_model.options.options = ["None", "Model", "Constant"]
        self._reference_model_group = ModelOptions("reference_model", **self.defaults)
        self._reference_model_group.options.observe(self.update_ref)

        self._reference_model = self._reference_model_group.data
        self._topography_group = TopographyOptions(**self.defaults)

        self._alpha_s = widgets.FloatText(
            min=0,
            value=1,
            description="Reference Model",
        )
        self._alpha_x = widgets.FloatText(
            min=0,
            value=1,
            description="Gradient EW",
        )
        self._alpha_y = widgets.FloatText(
            min=0,
            value=1,
            description="Gradient NS",
        )
        self._alpha_z = widgets.FloatText(
            min=0,
            value=1,
            description="Gradient Vertical",
        )
        self._s_norm = widgets.FloatText(
            value=2,
            description="",
            continuous_update=False,
        )
        self._x_norm = widgets.FloatText(
            value=2,
            description="",
            continuous_update=False,
        )
        self._y_norm = widgets.FloatText(
            value=2,
            description="",
            continuous_update=False,
        )
        self._z_norm = widgets.FloatText(
            value=2,
            description="",
            continuous_update=False,
        )
        self._norms = VBox(
            [
                Label("Norms"),
                self._s_norm,
                self._x_norm,
                self._y_norm,
                self._z_norm,
            ]
        )
        self._alphas = VBox(
            [
                Label("Scaling"),
                self._alpha_s,
                self._alpha_x,
                self._alpha_y,
                self._alpha_z,
            ]
        )
        self.bound_panel = HBox(
            [
                VBox([Label("Lower Bounds"), self._lower_bound_group.main]),
                VBox(
                    [
                        Label("Upper Bounds"),
                        self._upper_bound_group.main,
                    ]
                ),
            ]
        )
        self._mesh_octree = MeshOctreeOptions(**self.defaults)
        self.inversion_options = {
            "output name": self._ga_group_name,
            # "uncertainties": self._uncert_mode,
            "starting model": self._starting_model_group.main,
            # "background susceptibility": self._susceptibility_model.main,
            "regularization": VBox(
                [self._reference_model_group.main, HBox([self._alphas, self._norms])]
            ),
            "upper-lower bounds": self.bound_panel,
            "mesh": self._mesh_octree.main,
            "ignore values": VBox([self._ignore_values]),
            "optimization": self._optimization,
        }
        self.option_choices = widgets.Dropdown(
            options=list(self.inversion_options.keys()),
            value=list(self.inversion_options.keys())[0],
            disabled=False,
        )
        self.option_choices.observe(self.inversion_option_change, names="value")
        self.data_channel_choices = widgets.Dropdown(description="Component:")
        self.data_channel_panel = widgets.VBox([self.data_channel_choices])
        self.survey_type_panel = HBox([self.inversion_type])

        self.inversion_type.observe(self.inversion_type_observer, names="value")
        # self.mesh_1D = Mesh1DOptions(**self.defaults)
        self.objects.observe(self.object_observer, names="value")
        # self.data.observe(self.update_component_panel, names="value")
        self.data_channel_choices.observe(
            self.data_channel_choices_observer, names="value"
        )
        self.spatial_choices = widgets.Dropdown()
        self.spatial_choices.observe(self.spatial_option_change, names="value")
        self.spatial_panel = VBox([self.spatial_choices])
        super().__init__(**self.defaults)

        for item in ["window_width", "window_height", "resolution"]:
            getattr(self, item).observe(self.update_octree_param, names="value")

        self.write.on_click(self.write_trigger)

    @property
    def alphas(self):
        return self._alphas

    @property
    def alpha_s(self):
        return self._alpha_s

    @property
    def alpha_x(self):
        return self._alpha_x

    @property
    def alpha_y(self):
        return self._alpha_y

    @property
    def alpha_z(self):
        return self._alpha_z

    @property
    def beta_start(self):
        return self._beta_start

    @property
    def beta_start_options(self):
        return self._beta_start_options

    @property
    def chi_factor(self):
        return self._chi_factor

    @property
    def ignore_values(self):
        return self._ignore_values

    @property
    def max_iterations(self):
        return self._max_iterations

    @property
    def max_cg_iterations(self):
        return self._max_cg_iterations

    @property
    def n_cpu(self):
        """
        ipywidgets.IntText()
        """
        return self._n_cpu

    @property
    def max_ram(self):
        """
        ipywidgets.IntText()
        """
        return self._max_ram

    @property
    def mesh(self):
        return self._mesh

    @property
    def norms(self):
        return self._norms

    @property
    def s_norm(self):
        return self._s_norm

    @property
    def x_norm(self):
        return self._x_norm

    @property
    def y_norm(self):
        return self._y_norm

    @property
    def z_norm(self):
        return self._z_norm

    @property
    def optimization(self):
        return self._optimization

    @property
    def ga_group_name(self):
        return self._ga_group_name

    @property
    def reference_model(self):
        if self._reference_model_group.options.value == "Model":
            return self._reference_model_group.data.value
        elif self._reference_model_group.options.value == "Constant":
            return self._reference_model_group.constant.value
        else:
            return None

    @reference_model.setter
    def reference_model(self, value):
        if isinstance(value, float):
            self._reference_model_group.options.value = "Constant"
            self._reference_model_group.constant.value = value
        elif value is None:
            self._reference_model_group.options.value = "None"
        else:
            self._reference_model_group.data.value = value

    @property
    def reference_model_object(self):
        return self._reference_model_group.objects.value

    @property
    def starting_model(self):
        if self._starting_model_group.options.value == "Model":
            return self._starting_model_group.data.value
        elif self._starting_model_group.options.value == "Constant":
            return self._starting_model_group.constant.value
        else:
            return None

    @starting_model.setter
    def starting_model(self, value):
        if isinstance(value, float):
            self._starting_model_group.options.value = "Constant"
            self._starting_model_group.constant.value = value
        else:
            self._starting_model_group.data.value = value

    @property
    def starting_model_object(self):
        return self._starting_model_group.objects.value

    @property
    def lower_bound(self):
        if self._lower_bound_group.options.value == "Model":
            return self._lower_bound_group.data.value
        elif self._lower_bound_group.options.value == "Constant":
            return self._lower_bound_group.constant.value
        else:
            return None

    @lower_bound.setter
    def lower_bound(self, value):
        if isinstance(value, float):
            self._lower_bound_group.options.value = "Constant"
            self._lower_bound_group.constant.value = value
        elif value is None:
            self._lower_bound_group.options.value = "None"
        else:
            self._lower_bound_group.data.value = value

    @property
    def lower_bound_object(self):
        return self._lower_bound_group.objects.value

    @property
    def upper_bound(self):
        if self._upper_bound_group.options.value == "Model":
            return self._upper_bound_group.data.value
        elif self._upper_bound_group.options.value == "Constant":
            return self._upper_bound_group.constant.value
        else:
            return None

    @upper_bound.setter
    def upper_bound(self, value):
        if isinstance(value, float):
            self._upper_bound_group.options.value = "Constant"
            self._upper_bound_group.constant.value = value
        elif value is None:
            self._upper_bound_group.options.value = "None"
        else:
            self._upper_bound_group.data.value = value

    @property
    def upper_bound_object(self):
        return self._upper_bound_group.objects.value

    # @property
    # def susceptibility_model(self):
    #     return self._susceptibility_model

    @property
    def tol_cg(self):
        return self._tol_cg

    #
    # @property
    # def uncert_mode(self):
    #     return self._uncert_mode

    @property
    def data_count(self):
        """"""
        return self._data_count

    @property
    def forward_only(self):
        """"""
        return self._forward_only

    @property
    def inducing_field_strength(self):
        """"""
        return self._inducing_field_strength

    @property
    def inducing_field_inclination(self):
        """"""
        return self._inducing_field_inclination

    @property
    def inducing_field_declination(self):
        """"""
        return self._inducing_field_declination

    @property
    def lines(self):
        if getattr(self, "_lines", None) is None:
            self._lines = LineOptions(workspace=self._workspace, objects=self._objects)
            self.lines.lines.observe(self.update_selection, names="value")
        return self._lines

    @property
    def main(self):
        if getattr(self, "_main", None) is None:
            self._main = VBox(
                [
                    self.project_panel,
                    VBox(
                        [
                            self.objects,
                            self.survey_type_panel,
                        ],
                        layout=Layout(border="solid"),
                    ),
                    VBox(
                        [
                            Label("Select Data Components"),
                            HBox(
                                [
                                    self.data_channel_panel,
                                    self.window_selection,
                                ],
                            ),
                        ],
                        layout=Layout(border="solid"),
                    ),
                    VBox(
                        [
                            Label("Topography and Sensor Options"),
                            self.spatial_panel,
                        ],
                        layout=Layout(border="solid"),
                    ),
                    VBox(
                        [
                            Label("Inversion Parameters"),
                            HBox(
                                [
                                    self.option_choices,
                                    self.inversion_options[self.option_choices.value],
                                ],
                            ),
                        ],
                        layout=Layout(border="solid"),
                    ),
                    VBox(
                        [
                            Label("Output"),
                            self.forward_only,
                            self.export_directory,
                            self.write,
                            self.trigger,
                        ],
                        layout=Layout(border="solid"),
                    ),
                ]
            )
        return self._main

    @property
    def sensor(self):
        if getattr(self, "_sensor", None) is None:
            self._sensor = SensorOptions(
                workspace=self._workspace,
                objects=self._objects,
                **self.defaults,
            )
        return self._sensor

    @property
    def spatial_options(self):
        if getattr(self, "_spatial_options", None) is None:
            self._spatial_options = {
                "Topography": self.topography_group.main,
                "Sensor": self.sensor.main,
                "Line ID": self.lines.main,
            }
        return self._spatial_options

    @property
    def starting_channel(self):
        """"""
        return self._starting_channel

    @property
    def inversion_type(self):
        """"""
        return self._inversion_type

    @property
    def topography(self):
        if self._topography_group.options.value == "Object":
            return self._topography_group.data
        elif self._topography_group.options.value == "Relative to sensor":
            return self._topography_group.offset
        elif self._topography_group.options.value == "Constant":
            return self._topography_group.constant

    @topography.setter
    def topography(self, value):
        if isinstance(value, float):
            self._topography_group.constant.value = value
        else:
            self._topography_group.data.value = value

    @property
    def topography_object(self):
        return self._topography_group.objects

    @property
    def topography_group(self):
        return self._topography_group

    @property
    def workspace(self):
        """
        Target geoh5py workspace
        """
        if (
            getattr(self, "_workspace", None) is None
            and getattr(self, "_h5file", None) is not None
        ):
            self.workspace = Workspace(self.h5file)
        return self._workspace

    @workspace.setter
    def workspace(self, workspace):
        assert isinstance(workspace, Workspace), f"Workspace must of class {Workspace}"
        self._workspace = workspace
        self._h5file = workspace.h5file

        # Refresh the list of objects
        self.update_objects_list()

        # Check for startup
        # if getattr(self, "_inversion_parameters", None) is not None:
        #     # self.inversion_parameters.update_workspace(workspace)
        self.lines.workspace = workspace
        self.sensor.workspace = workspace
        self._topography_group.workspace = workspace
        self._reference_model_group.workspace = workspace
        self._starting_model_group.workspace = workspace
        self._mesh_octree.workspace = workspace

        export_path = os.path.abspath(os.path.dirname(self.h5file))
        if not os.path.exists(export_path):
            os.mkdir(export_path)

        self.export_directory._set_form_values(export_path, "")
        self.export_directory._apply_selection()

        self._file_browser.reset(
            path=self.working_directory,
            filename=path.basename(self._h5file),
        )
        self._file_browser._apply_selection()

    @property
    def write(self):
        """"""
        return self._write

    # Observers
    def update_ref(self, _):
        alphas = [alpha.value for alpha in self.alphas.children]
        if self._reference_model_group.options.value == "None":
            alphas[0] = 0.0
        else:
            alphas[0] = 1.0
        self.alphas.value = ", ".join(list(map(str, alphas)))

    def inversion_option_change(self, _):
        self._main.children[4].children[1].children = [
            self.option_choices,
            self.inversion_options[self.option_choices.value],
        ]

    def initial_beta_change(self, _):
        if self._beta_start_options.value == "ratio":
            self._beta_start.description = "phi_d/phi_m"
        else:
            self._beta_start.description = ""

    def trigger_click(self, _):
        """"""

        self.run(self.params)

        self.trigger.button_style = ""

    def inversion_type_observer(self, _):
        """
        Change the application on change of system
        """
        start_channel = 0
        if self.inversion_type.value in ["magnetic vector", "magnetic scalar"]:
            data_type_list = [
                "tmi",
                "bx",
                "by",
                "bz",
                "bxx",
                "bxy",
                "bxz",
                "byy",
                "byz",
                "bzz",
            ]

        else:
            data_type_list = [
                # "gx",
                # "gy",
                "gz",
                "gxx",
                "gxy",
                "gxz",
                "gyy",
                "gyz",
                "gzz",
                "uv",
            ]

        system_specs = {}
        for key in data_type_list:
            system_specs[key] = key

        # Remove line_id from choices
        self.spatial_choices.options = list(self.spatial_options.keys())[:2]

        # Switch mesh options
        # self.inversion_parameters._mesh = self._mesh_octree
        # self.inversion_parameters.inversion_options["mesh"] = self._mesh_octree.main
        #
        # self.inversion_parameters.reference_model.options.options = [
        #     "None",
        #     "Model",
        #     "Constant",
        # ]
        # self.inversion_parameters.reference_model.options.value = "Constant"
        flag = self.inversion_type.value
        #
        # self.inversion_parameters.lower_bound.value = ""
        # self.inversion_parameters.upper_bound.value = ""
        # self.inversion_parameters.ignore_values.value = "-99999"

        # else:
        #     tx_offsets = self.em_system_specs[self.inversion_type.value]["tx_offsets"]
        #     self.sensor.offset.value = ", ".join(
        #         [
        #             str(offset)
        #             for offset in self.em_system_specs[self.inversion_type.value][
        #                 "bird_offset"
        #             ]
        #         ]
        #     )
        #     uncertainties = self.em_system_specs[self.inversion_type.value][
        #         "uncertainty"
        #     ]
        #
        #     # if start_channel is None:
        #     start_channel = self.em_system_specs[self.inversion_type.value][
        #         "channel_start_index"
        #     ]
        #     if self.em_system_specs[self.inversion_type.value]["type"] == "time":
        #         labels = ["Time (s)"] * len(
        #             self.em_system_specs[self.inversion_type.value]["channels"]
        #         )
        #     else:
        #         labels = ["Frequency (Hz)"] * len(
        #             self.em_system_specs[self.inversion_type.value]["channels"]
        #         )
        #
        #     system_specs = {}
        #     for key, time in self.em_system_specs[self.inversion_type.value][
        #         "channels"
        #     ].items():
        #         system_specs[key] = f"{time:.5e}"
        #
        #     self.spatial_choices.options = list(self.spatial_options.keys())
        #
        #     self.inversion_parameters.reference_model.options.options = [
        #         "Best-fitting halfspace",
        #         "Model",
        #         "Constant",
        #     ]
        #     self.inversion_parameters.reference_model.options.value = (
        #         "Best-fitting halfspace"
        #     )
        #     self.inversion_parameters.lower_bound.value = "1e-5"
        #     self.inversion_parameters.upper_bound.value = "10"
        #     self.inversion_parameters.ignore_values.value = "<0"
        #
        #     # Switch mesh options
        #     self.inversion_parameters._mesh = self.mesh_1D
        #     self.inversion_parameters.inversion_options["mesh"] = self.mesh_1D.main
        #     flag = "EM1D"

        self._reference_model_group.constant.description = inversion_defaults()[
            "units"
        ][flag]
        self._reference_model_group.constant.value = inversion_defaults()[
            "reference_value"
        ][flag]
        self._reference_model_group.description.value = (
            "Reference " + inversion_defaults()["property"][flag]
        )
        self._starting_model_group.constant.description = inversion_defaults()["units"][
            flag
        ]
        self._starting_model_group.constant.value = inversion_defaults()[
            "starting_value"
        ][flag]
        self._starting_model_group.description.value = (
            "Starting " + inversion_defaults()["property"][flag]
        )
        self.spatial_choices.value = self.spatial_choices.options[0]
        data_channel_options = {}
        self.data_channel_choices.options = data_type_list

        if self.workspace.get_entity(self.objects.value):
            obj, _ = self.get_selected_entities()
            options = [
                [name, obj.get_data(name)[0].uid]
                for name in sorted(obj.get_data_list())
                if "visual parameter" not in name.lower()
            ]
        else:
            options = []
            # if hasattr(self.data_channel_choices, "data_channel_options"):
            #     for (
            #         key,
            #         data_widget,
            #     ) in self.data_channel_choices.data_channel_options.items():
            #         data_widget.children[2].options = options

        for ind, key in enumerate(system_specs):
            if ind + 1 < start_channel:
                continue
            #
            # if len(tx_offsets) > 1:
            #     offsets = tx_offsets[ind]
            # else:
            #     offsets = tx_offsets[0]

            # channel_options = ChannelOptions(
            #     key,
            #     labels[ind],
            #     uncertainties=", ".join(
            #         [str(uncert) for uncert in uncertainties[ind][:2]]
            #     ),
            #     # offsets=", ".join([str(offset) for offset in offsets]),
            # )

            def channel_setter(caller):

                channel = caller["owner"]
                data_widget = getattr(self, f"{channel.header}_group")

                entity = self.workspace.get_entity(self.objects.value)[0]
                if channel.value is None or channel.value not in [
                    child.uid for child in entity.children
                ]:
                    data_widget.children[0].value = False
                    data_widget.children[3].children[0].value = 1.0
                else:
                    data_widget.children[0].value = True
                    values = self.workspace.get_entity(channel.value)[0].values
                    if values is not None and values.dtype in [
                        np.float32,
                        np.float64,
                        np.int32,
                    ]:
                        data_widget.children[3].children[0].value = np.percentile(
                            np.abs(values[~np.isnan(values)]), 5
                        )

                # Trigger plot update
                if self.data_channel_choices.value == channel.header:
                    self.plotting_data = channel.value
                    self.refresh.value = False
                    self.refresh.value = True

            # def floor_setter(caller):
            #     channel = caller["owner"]
            #     data_widget = getattr(self, f"{channel.header}_group")
            #     value = channel.value
            #     data_widget.children[3].children[1].value = None
            #     channel.value = value

            def uncert_setter(caller):
                channel = caller["owner"]
                data_widget = getattr(self, f"{channel.header}_group")

                if isinstance(channel, FloatText) and channel.value > 0:
                    data_widget.children[3].children[1].value = None
                elif channel.value is not None:
                    data_widget.children[3].children[0].value = 0.0

            if hasattr(self, f"{key}_group"):
                data_channel_options[key] = getattr(self, f"{key}_group", None)
            else:
                setattr(
                    self,
                    f"{key}_channel_bool",
                    Checkbox(
                        value=False,
                        indent=False,
                        description="Active",
                    ),
                )
                setattr(self, f"{key}_channel", Dropdown(description="Channel:"))
                setattr(
                    self, f"{key}_uncertainty_floor", FloatText(description="Floor:")
                )
                setattr(
                    self,
                    f"{key}_uncertainty_channel",
                    Dropdown(
                        description="[Optional] Channel:",
                        style={"description_width": "initial"},
                    ),
                )
                setattr(
                    self,
                    f"{key}_group",
                    VBox(
                        [
                            getattr(self, f"{key}_channel_bool"),
                            getattr(self, f"{key}_channel"),
                            Label("Uncertainties"),
                            VBox(
                                [
                                    getattr(self, f"{key}_uncertainty_floor"),
                                    getattr(self, f"{key}_uncertainty_channel"),
                                ]
                            ),
                        ]
                    ),
                )
                data_channel_options[key] = getattr(self, f"{key}_group")
                data_channel_options[key].children[1].options = [["", None]] + options
                data_channel_options[key].children[1].header = key
                data_channel_options[key].children[1].observe(
                    channel_setter, names="value"
                )
                data_channel_options[key].children[3].children[1].options = [
                    ["", None]
                ] + options
                data_channel_options[key].children[3].children[0].observe(
                    uncert_setter, names="value"
                )
                data_channel_options[key].children[3].children[1].observe(
                    uncert_setter, names="value"
                )
                data_channel_options[key].children[3].children[0].header = key
                data_channel_options[key].children[3].children[1].header = key

            data_channel_options[key].children[1].value = find_value(options, [key])

            # if self.inversion_type.value not in [
            #     "magnetic vector",
            #     "magnetic scalar",
            #     "gravity",
            # ]:
            #     data_channel_options[key].children[1].value = channel
            # else:
            #     data_channel_options[key].children[1].layout.visibility = "hidden"
            #     data_channel_options[key].children[4].layout.visibility = "hidden"

        # if len(data_channel_options) > 0:
        self.data_channel_choices.value = list(data_channel_options.keys())[0]
        self.data_channel_choices.data_channel_options = data_channel_options
        self.data_channel_panel.children = [
            self.data_channel_choices,
            data_channel_options[self.data_channel_choices.value],
        ]

        # self.update_component_panel(None)

        # if (
        #     self.inversion_type.value
        #     not in ["magnetic vector", "magnetic scalar", "gravity"]
        #     and self.em_system_specs[self.inversion_type.value]["type"] == "frequency"
        # ):
        #     self.inversion_parameters.option_choices.options = list(
        #         self.inversion_parameters.inversion_options.keys()
        #     )
        # else:
        #     self.inversion_parameters.option_choices.options = [
        #         key
        #         for key in self.inversion_parameters.inversion_options.keys()
        #         if key != "background susceptibility"
        #     ]

        self.write.button_style = "warning"
        self.trigger.button_style = "danger"

        if self.inversion_type.value in ["magnetic vector", "magnetic scalar"]:
            self.survey_type_panel.children = [
                self.inversion_type,
                VBox(
                    [
                        Label("Inducing Field Parameters"),
                        self.inducing_field_strength,
                        self.inducing_field_inclination,
                        self.inducing_field_declination,
                    ]
                ),
            ]
        else:
            self.survey_type_panel.children = [self.inversion_type]

    def object_observer(self, _):

        self.resolution.indices = None

        if self.workspace.get_entity(self.objects.value):
            self.update_data_list(None)
            self.sensor.update_data_list(None)
            self.lines.update_data_list(None)
            self.lines.update_line_list(None)

            # for aem_system, specs in self.em_system_specs.items():
            #     if any(
            #         [
            #             specs["flag"] in channel
            #             for channel in self.data.uid_name_map.values()
            #         ]
            #     ):
            #         self.inversion_type.value = aem_system

            self.inversion_type_observer(None)

            # if hasattr(self.data_channel_choices, "data_channel_options"):
            #     for (
            #         key,
            #         data_widget,
            #     ) in self.data_channel_choices.data_channel_options.items():
            #         data_widget.children[2].options = self.data.options
            #         value = find_value(self.data.options, [key])
            #         data_widget.children[2].value = value

            self.write.button_style = "warning"
            self.trigger.button_style = "danger"

    # def update_component_panel(self, _):
    #     if self.workspace.get_entity(self.objects.value):
    #         _, data_list = self.get_selected_entities()
    #         options = [[data.name, data.uid] for data in data_list]
    #         if hasattr(self.data_channel_choices, "data_channel_options"):
    #             for (
    #                 key,
    #                 data_widget,
    #             ) in self.data_channel_choices.data_channel_options.items():
    #                 data_widget.children[2].options = options
    #
    #                 if find_value(options, [key]) in options:
    #                     data_widget.children[2].value = find_value(options, [key])

    def data_channel_choices_observer(self, _):
        if hasattr(
            self.data_channel_choices, "data_channel_options"
        ) and self.data_channel_choices.value in (
            self.data_channel_choices.data_channel_options.keys()
        ):
            data_widget = self.data_channel_choices.data_channel_options[
                self.data_channel_choices.value
            ]
            self.data_channel_panel.children = [self.data_channel_choices, data_widget]

            if (
                self.workspace.get_entity(self.objects.value)
                and data_widget.children[1].value is None
            ):
                _, data_list = self.get_selected_entities()
                options = [[data.name, data.uid] for data in data_list]
                data_widget.children[1].value = find_value(
                    options, [self.data_channel_choices.value]
                )

            self.plotting_data = data_widget.children[1].value
            self.refresh.value = False
            self.refresh.value = True

        self.write.button_style = "warning"
        self.trigger.button_style = "danger"

    def spatial_option_change(self, _):
        self.spatial_panel.children = [
            self.spatial_choices,
            self.spatial_options[self.spatial_choices.value],
        ]
        self.write.button_style = "warning"
        self.trigger.button_style = "danger"

    def update_octree_param(self, _):
        dl = self.resolution.value
        self._mesh_octree.u_cell_size.value = f"{dl/2:.0f}"
        self._mesh_octree.v_cell_size.value = f"{dl / 2:.0f}"
        self._mesh_octree.z_cell_size.value = f"{dl / 2:.0f}"
        self._mesh_octree.depth_core.value = np.ceil(
            np.min([self.window_width.value, self.window_height.value]) / 2.0
        )
        self._mesh_octree.horizontal_padding.value = (
            np.max([self.window_width.value, self.window_width.value]) / 2
        )
        self.resolution.indices = None
        self.write.button_style = "warning"
        self.trigger.button_style = "danger"

    def update_selection(self, _):
        self.highlight_selection = {self.lines.data.value: self.lines.lines.value}
        self.refresh.value = False
        self.refresh.value = True

    def write_trigger(self, _):

        # input_dict = {
        #     "out_group": self.inversion_parameters.out_group.value,
        #     "workspace": os.path.abspath(self.h5file),
        #     "save_to_geoh5": os.path.abspath(self.h5file),
        #     "mesh": "Mesh",
        # }
        # if self.inversion_type.value in [
        #     "gravity",
        #     "magnetic vector",
        #     "magnetic scalar",
        # ]:
        #     input_dict["inversion_type"] = self.inversion_type.value.lower()
        #
        #     if input_dict["inversion_type"] in ["mvi", "magnetics"]:
        #         input_dict["inducing_field_aid"] = string_2_list(
        #             self.inducing_field_strength.value
        #         )
        #
        #     # Octree mesh parameters
        #     input_dict["core_cell_size"] = string_2_list(
        #         self._mesh_octree.core_cell_size.value
        #     )
        #     input_dict["octree_levels_topo"] = string_2_list(
        #         self._mesh_octree.octree_levels_topo.value
        #     )
        #     input_dict["octree_levels_obs"] = string_2_list(
        #         self._mesh_octree.octree_levels_obs.value
        #     )
        #     input_dict["depth_core"] = {"value": self._mesh_octree.depth_core.value}
        #     input_dict["max_distance"] = self._mesh_octree.max_distance.value
        #     p_d = string_2_list(self._mesh_octree.padding_distance.value)
        #     input_dict["padding_distance"] = [
        #         [p_d[0], p_d[1]],
        #         [p_d[2], p_d[3]],
        #         [p_d[4], p_d[5]],
        #     ]
        #
        # else:
        #     input_dict["system"] = self.inversion_type.value
        #     input_dict["lines"] = {
        #         str(self.lines.data.value): [
        #             str(line) for line in self.lines.lines.value
        #         ]
        #     }
        #
        #     input_dict["mesh 1D"] = [
        #         self.mesh_1D.hz_min.value,
        #         self.mesh_1D.hz_expansion.value,
        #         self.mesh_1D.n_cells.value,
        #     ]
        #     input_dict["uncertainty_mode"] = self.inversion_parameters.uncert_mode.value
        #
        # input_dict["chi_factor"] = self.inversion_parameters.chi_factor.value
        # input_dict["max_iterations"] = self.inversion_parameters.max_iterations.value
        # input_dict[
        #     "max_cg_iterations"
        # ] = self.inversion_parameters.max_cg_iterations.value
        #
        # input_dict["n_cpu"] = self.inversion_parameters.n_cpu.value
        # input_dict["max_ram"] = self.inversion_parameters.max_ram.value
        #
        # if self.inversion_parameters.beta_start_options.value == "value":
        #     input_dict["initial_beta"] = self.inversion_parameters.beta_start.value
        # else:
        #     input_dict[
        #         "initial_beta_ratio"
        #     ] = self.inversion_parameters.beta_start.value
        #
        # input_dict["tol_cg"] = self.inversion_parameters.tol_cg.value
        # input_dict["ignore_values"] = self.inversion_parameters.ignore_values.value
        # input_dict["resolution"] = self.resolution.value
        # input_dict["window"] = {
        #     "center_x": self.center_x.value,
        #     "center_y": self.center_y.value,
        #     "width": self.width.value,
        #     "height": self.height.value,
        #     "azimuth": self.azimuth.value,
        # }
        # input_dict["alphas"] = string_2_list(self.inversion_parameters.alphas.value)
        #
        # ref_type = self.inversion_parameters.reference_model.options.value.lower()
        #
        # if ref_type == "model":
        #     input_dict["reference_model"] = {
        #         ref_type: {
        #             str(self.inversion_parameters.reference_model.objects.value): str(
        #                 self.inversion_parameters.reference_model.data.value
        #             )
        #         }
        #     }
        # else:
        #     input_dict["reference_model"] = {
        #         ref_type: self.inversion_parameters.reference_model.value.value
        #     }
        # start_type = self.inversion_parameters.starting_model.options.value.lower()
        #
        # if start_type == "model":
        #     input_dict["starting_model"] = {
        #         start_type: {
        #             str(self.inversion_parameters.starting_model.objects.value): str(
        #                 self.inversion_parameters.starting_model.data.value
        #             )
        #         }
        #     }
        # else:
        #     input_dict["starting_model"] = {
        #         start_type: self.inversion_parameters.starting_model.value.value
        #     }
        #
        # if self.inversion_parameters.susceptibility_model.options.value != "None":
        #     susc_type = (
        #         self.inversion_parameters.susceptibility_model.options.value.lower()
        #     )
        #
        #     if susc_type == "model":
        #         input_dict["susceptibility_model"] = {
        #             susc_type: {
        #                 str(
        #                     self.inversion_parameters.susceptibility_model.objects.value
        #                 ): str(
        #                     self.inversion_parameters.susceptibility_model.data.value
        #                 )
        #             }
        #         }
        #     else:
        #         input_dict["susceptibility_model"] = {
        #             susc_type: self.inversion_parameters.susceptibility_model.value.value
        #         }
        #
        # input_dict["model_norm"] = string_2_list(self.inversion_parameters.norms.value)
        #
        # if len(input_dict["model_norm"]) not in [4, 12]:
        #     print(
        #         f"Norm values should be 4 or 12 values. List of {len(input_dict['model_norm'])} values provided"
        #     )
        #
        # if len(self.inversion_parameters.lower_bound.value) > 0:
        #     input_dict["lower_bound"] = string_2_list(
        #         self.inversion_parameters.lower_bound.value
        #     )
        #
        # if len(self.inversion_parameters.upper_bound.value) > 0:
        #     input_dict["upper_bound"] = string_2_list(
        #         self.inversion_parameters.upper_bound.value
        #     )
        #
        # input_dict["data"] = {}
        # input_dict["data"]["type"] = "GA_object"
        # input_dict["data"]["name"] = str(self.objects.value)
        #
        # if hasattr(self.data_channel_choices, "data_channel_options"):
        #     channel_param = {}
        #
        #     for (
        #         key,
        #         data_widget,
        #     ) in self.data_channel_choices.data_channel_options.items():
        #         if data_widget.children[0].value is False:
        #             continue
        #
        #         channel_param[key] = {}
        #         channel_param[key]["name"] = str(data_widget.children[2].value)
        #         channel_param[key]["uncertainties"] = string_2_list(
        #             data_widget.children[3].value
        #         )
        #         channel_param[key]["offsets"] = string_2_list(
        #             data_widget.children[4].value
        #         )
        #
        #         if self.inversion_type.value not in [
        #             "gravity",
        #             "magnetic vector",
        #             "magnetic scalar",
        #         ]:
        #             channel_param[key]["value"] = string_2_list(
        #                 data_widget.children[1].value
        #             )
        #         if (
        #             self.inversion_type.value
        #             in ["gravity", "magnetic vector", "magnetic scalar"]
        #             and self.azimuth.value != 0
        #             and key not in ["tmi", "gz"]
        #         ):
        #             print(
        #                 f"Gradient data with rotated window is currently not supported"
        #             )
        #             self.trigger.button_style = "danger"
        #             return
        #
        #     input_dict["data"]["channels"] = channel_param
        #
        # if self.sensor.options.value == "sensor location + (dx, dy, dz)":
        #     input_dict["receivers_offset"] = {
        #         "constant": string_2_list(self.sensor.offset.value)
        #     }
        # else:
        #     input_dict["receivers_offset"] = {
        #         "radar_drape": string_2_list(self.sensor.offset.value)
        #         + [self.sensor.data.value]
        #     }
        #
        # if self.topography.options.value == "Object":
        #     if self.topography.objects.value is None:
        #         input_dict["topography"] = None
        #     else:
        #         input_dict["topography"] = {
        #             "GA_object": {
        #                 "name": str(self.topography.objects.value),
        #                 "data": str(self.topography.data.value),
        #             }
        #         }
        # elif self.topography.options.value == "Relative to Sensor":
        #     input_dict["topography"] = {"draped": self.topography.offset.value}
        # else:
        #     input_dict["topography"] = {"constant": self.topography.constant.value}
        #
        # if self.forward_only.value:
        #     input_dict["forward_only"] = []
        #
        # checks = [key for key, val in input_dict.items() if val is None]
        #
        # if len(list(input_dict["data"]["channels"].keys())) == 0:
        #     checks += ["'Channel' for at least one data component."]
        #
        # if len(checks) > 0:
        #     print(f"Required value for {checks}")
        #     self.trigger.button_style = "danger"
        # else:
        #     self.write.button_style = ""
        #     file = f"{os.path.join(self.export_directory.selected_path, self.inversion_parameters.out_group.value)}.json"
        #     with open(file, "w") as f:
        #         json.dump(input_dict, f, indent=4)
        #     self.trigger.button_style = "success"

        for key in self.__dict__:
            try:
                attr = getattr(self, key)
                if isinstance(attr, Widget):
                    setattr(self.params, key, attr.value)
                elif isinstance(attr, ModelOptions):
                    model_group = attr.identifier
                    for label in ["", "_object"]:
                        setattr(
                            self.params,
                            model_group + label,
                            getattr(self, model_group + label),
                        )
                elif isinstance(attr, MeshOctreeOptions):
                    for O_key in self._mesh_octree.__dict__:
                        value = getattr(self._mesh_octree, O_key[1:])
                        if isinstance(value, Widget):
                            setattr(self.params, O_key, value.value)
                        else:
                            setattr(self.params, O_key, value)
            except AttributeError:
                continue

        for key in self.data_channel_choices.options:
            widget = getattr(self, f"{key}_uncertainty_channel")
            if widget.value is not None:
                setattr(self.params, f"{key}_uncertainty", widget.value)
            else:
                widget = getattr(self, f"{key}_uncertainty_floor")
                setattr(self.params, f"{key}_uncertainty", widget.value)

        self.params.out_group.name = self._ga_group_name.value
        self.params.write_input_file(name=self._ga_group_name.value)

        self.write.button_style = ""
        self.trigger.button_style = "success"

    @staticmethod
    def run(params):

        if isinstance(params, MagneticVectorParams):

            os.system(
                "start cmd.exe @cmd /k "
                + 'python -m geoapps.drivers.magnetic_vector_inversion "'
                + f"{params.input_file.filepath}"
            )

        # elif params.inversion_type == "magnetic scalar":
        #     from geoapps.drivers.magnetic_scalar_inversion import MagneticScalarDriver
        #     driver = MagneticScalarDriver(params)
        # elif params.inversion_type == "gravity":
        #     from geoapps.drivers.grav_inversion import GravityDriver
        #     driver = GravityDriver(params)
        else:
            raise ValueError(
                "Parameter 'inversion_type' must be one of "
                "'magnetic vector', 'magnetic scalar' or 'gravity'"
            )

        # driver.run()


def get_inversion_output(h5file, group_name):
    """
    Recover an inversion iterations from a ContainerGroup comments.
    """
    workspace = Workspace(h5file)
    out = {"time": [], "iteration": [], "phi_d": [], "phi_m": [], "beta": []}

    if workspace.get_entity(group_name):
        group = workspace.get_entity(group_name)[0]

        for comment in group.comments.values:
            if "Iteration" in comment["Author"]:
                out["iteration"] += [np.int(comment["Author"].split("_")[1])]
                out["time"] += [comment["Date"]]
                values = json.loads(comment["Text"])
                out["phi_d"] += [float(values["phi_d"])]
                out["phi_m"] += [float(values["phi_m"])]
                out["beta"] += [float(values["beta"])]

        if len(out["iteration"]) > 0:
            out["iteration"] = np.hstack(out["iteration"])
            ind = np.argsort(out["iteration"])
            out["iteration"] = out["iteration"][ind]
            out["phi_d"] = np.hstack(out["phi_d"])[ind]
            out["phi_m"] = np.hstack(out["phi_m"])[ind]
            out["time"] = np.hstack(out["time"])[ind]

    return out


def plot_convergence_curve(h5file):
    """"""
    workspace = Workspace(h5file)
    names = [
        group.name for group in workspace.groups if isinstance(group, ContainerGroup)
    ]
    objects = widgets.Dropdown(
        options=names,
        value=names[0],
        description="Inversion Group:",
    )

    def plot_curve(objects):

        inversion = workspace.get_entity(objects)[0]
        result = None
        if getattr(inversion, "comments", None) is not None:
            if inversion.comments.values is not None:
                result = get_inversion_output(workspace.h5file, objects)
                iterations = result["iteration"]
                phi_d = result["phi_d"]
                phi_m = result["phi_m"]

                ax1 = plt.subplot()
                ax2 = ax1.twinx()
                ax1.plot(iterations, phi_d, linewidth=3, c="k")
                ax1.set_xlabel("Iterations")
                ax1.set_ylabel(r"$\phi_d$", size=16)
                ax2.plot(iterations, phi_m, linewidth=3, c="r")
                ax2.set_ylabel(r"$\phi_m$", size=16)

        return result

    interactive_plot = widgets.interactive(plot_curve, objects=objects)

    return interactive_plot


class SensorOptions(ObjectDataSelection):
    """
    Define the receiver spatial parameters
    """

    _options = None

    def __init__(self, **kwargs):
        self.defaults.update(**kwargs)
        self._offset = Text(description="(dx, dy, dz) (+ve up)", value="0, 0, 0")
        self._constant = FloatText(
            description="Constant elevation (m)",
        )
        if "offset" in self.defaults.keys():
            self._offset.value = self.defaults["offset"]

        self.option_list = {
            "sensor location + (dx, dy, dz)": self.offset,
            "topo + radar + (dx, dy, dz)": VBox(
                [
                    self.offset,
                ]
            ),
        }
        self.options.observe(self.update_options, names="value")

        super().__init__(**self.defaults)

        self.option_list["topo + radar + (dx, dy, dz)"].children = [
            self.offset,
            self.data,
        ]
        self.data.description = "Radar (Optional):"
        self.data.style = {"description_width": "initial"}

    @property
    def main(self):
        if self._main is None:
            self._main = VBox([self.options, self.option_list[self.options.value]])

        return self._main

    @property
    def offset(self):
        return self._offset

    @property
    def options(self):

        if getattr(self, "_options", None) is None:
            self._options = widgets.RadioButtons(
                options=[
                    "sensor location + (dx, dy, dz)",
                    "topo + radar + (dx, dy, dz)",
                ],
                description="Define by:",
            )
        return self._options

    def update_options(self, _):
        self.main.children = [
            self.options,
            self.option_list[self.options.value],
        ]


class MeshOctreeOptions(ObjectDataSelection):
    """
    Widget used for the creation of an octree meshes
    """

    def __init__(self, **kwargs):
        self._mesh_from_params = Checkbox(value=False, description="Create")
        self._mesh_from_params.observe(self.from_params_choice, names="value")
        self._u_cell_size = widgets.FloatText(
            value=25.0,
            description="",
        )
        self._v_cell_size = widgets.FloatText(
            value=25.0,
            description="",
        )
        self._z_cell_size = widgets.FloatText(
            value=25.0,
            description="",
        )
        self._octree_levels_topo = widgets.Text(
            value="0, 0, 0, 2",
            description="# Cells below topography",
        )
        self._octree_levels_obs = widgets.Text(
            value="5, 5, 5, 5",
            description="# Cells below sensors",
        )
        self._depth_core = FloatText(
            value=500,
            description="Minimum depth (m)",
        )
        self._horizontal_padding = widgets.FloatText(
            value=1000.0,
            description="Horizontal padding (m)",
        )
        self._vertical_padding = widgets.FloatText(
            value=1000.0,
            description="Vertical padding (m)",
        )
        self._max_distance = FloatText(
            value=1000,
            description="Maximum distance (m)",
        )
        self._parameters = widgets.VBox(
            [
                Label("Core cell size (u, v, z)"),
                self._u_cell_size,
                self._v_cell_size,
                self._z_cell_size,
                Label("Refinement Layers"),
                self._octree_levels_topo,
                self._octree_levels_obs,
                self._max_distance,
                Label("Dimensions"),
                self._horizontal_padding,
                self._vertical_padding,
                self._depth_core,
            ]
        )
        self._main = VBox([self.objects, self.mesh_from_params])

        super().__init__(**kwargs)

    @property
    def main(self):
        return self._main

    @property
    def mesh(self):
        return self._objects

    @property
    def mesh_from_params(self):
        return self._mesh_from_params

    @property
    def u_cell_size(self):
        return self._u_cell_size

    @property
    def v_cell_size(self):
        return self._v_cell_size

    @property
    def z_cell_size(self):
        return self._z_cell_size

    @property
    def depth_core(self):
        return self._depth_core

    @property
    def max_distance(self):
        return self._max_distance

    @property
    def octree_levels_obs(self):
        return self._octree_levels_obs

    @octree_levels_obs.getter
    def octree_levels_obs(self):
        return string_2_list(self._octree_levels_obs.value)

    @property
    def octree_levels_topo(self):
        return self._octree_levels_topo

    @octree_levels_topo.getter
    def octree_levels_topo(self):
        return string_2_list(self._octree_levels_topo.value)

    @property
    def horizontal_padding(self):
        return self._horizontal_padding

    @property
    def vertical_padding(self):
        return self._vertical_padding

    @property
    def main(self):
        return self._main

    def from_params_choice(self, _):
        if self._mesh_from_params.value:
            self._main.children = [
                self.objects,
                self.mesh_from_params,
                self._parameters,
            ]
        else:
            self._main.children = [self.objects, self.mesh_from_params]


class Mesh1DOptions:
    """
    Widget used for the creation of a 1D mesh
    """

    def __init__(self, **kwargs):
        self._hz_expansion = FloatText(
            value=1.05,
            description="Expansion factor:",
        )
        self._hz_min = FloatText(
            value=10.0,
            description="Smallest cell (m):",
        )
        self._n_cells = FloatText(
            value=25.0,
            description="Number of cells:",
        )
        self.cell_count = Label(f"Max depth: {self.count_cells():.2f} m")
        self.n_cells.observe(self.update_hz_count)
        self.hz_expansion.observe(self.update_hz_count)
        self.hz_min.observe(self.update_hz_count)
        self._main = VBox(
            [
                Label("1D Mesh"),
                self.hz_min,
                self.hz_expansion,
                self.n_cells,
                self.cell_count,
            ]
        )

        for obj in self.__dict__:
            if hasattr(getattr(self, obj), "style"):
                getattr(self, obj).style = {"description_width": "initial"}

        for key, value in kwargs.items():
            if hasattr(self, "_" + key):
                try:
                    getattr(self, key).value = value
                except:
                    pass

    def count_cells(self):
        return (
            self.hz_min.value * self.hz_expansion.value ** np.arange(self.n_cells.value)
        ).sum()

    def update_hz_count(self, _):
        self.cell_count.value = f"Max depth: {self.count_cells():.2f} m"

    @property
    def hz_expansion(self):
        """"""
        return self._hz_expansion

    @property
    def hz_min(self):
        """"""
        return self._hz_min

    @property
    def n_cells(self):
        """"""
        return self._n_cells

    @property
    def main(self):
        return self._main


class ModelOptions(ObjectDataSelection):
    """
    Widgets for the selection of model options
    """

    def __init__(self, identifier: str = None, **kwargs):
        self._units = "Units"
        self._identifier = identifier
        self._object_types = (BlockModel, Octree, Surface)
        self._options = widgets.RadioButtons(
            options=["Model", "Constant", "None"],
            value="Constant",
            disabled=False,
        )
        self._options.observe(self.update_panel, names="value")
        self.objects.description = "Object"
        self.data.description = "Values"
        self._constant = FloatText(description=self.units)
        self._description = Label()

        super().__init__(**kwargs)

        self.selection_widget = self.main
        self._main = widgets.VBox(
            [self._description, widgets.VBox([self._options, self._constant])]
        )

        # for key, value in kwargs.items():
        #     if self.identifier in key:
        #         if "object" in key:
        #             self.objects.value = value
        #         elif isinstance(value, float):
        #             self.constant.value = value
        #             self.options.value = "Constant"
        #         elif isinstance(value, UUID):
        #             self.data.value = value
        #             self.options.value = "Model"
        #         else:
        #             self.options.value = "None"

    def update_panel(self, _):

        if self._options.value == "Model":
            self._main.children[1].children = [self._options, self.selection_widget]
            self._main.children[1].children[1].layout.visibility = "visible"
        elif self._options.value == "Constant":
            self._main.children[1].children = [self._options, self._constant]
            self._main.children[1].children[1].layout.visibility = "visible"
        else:
            self._main.children[1].children[1].layout.visibility = "hidden"

    @property
    def constant(self):
        return self._constant

    @property
    def description(self):
        return self._description

    @property
    def identifier(self):
        return self._identifier

    @property
    def options(self):
        return self._options

    @property
    def units(self):
        return self._units

    @units.setter
    def units(self, value):
        self._units = value
        self._constant.description = value