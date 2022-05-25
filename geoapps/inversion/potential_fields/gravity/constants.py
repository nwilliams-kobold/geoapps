#  Copyright (c) 2022 Mira Geoscience Ltd.
#
#  This file is part of geoapps.
#
#  geoapps is distributed under the terms and conditions of the MIT License
#  (see LICENSE file at the root of this source code package).

from uuid import UUID

from geoh5py.objects import Grid2D, Points, Surface

from geoapps.inversion import default_ui_json as base_default_ui_json

################# defaults ##################

inversion_defaults = {
    "title": "SimPEG gravity inversion",
    "inversion_type": "gravity",
    "geoh5": None,  # Must remain at top of list for notebook app initialization
    "forward_only": False,
    "topography_object": None,
    "topography": None,
    "data_object": None,
    "gz_channel": None,
    "gz_uncertainty": 1.0,
    "guv_channel": None,
    "guv_uncertainty": 1.0,
    "gxy_channel": None,
    "gxy_uncertainty": 1.0,
    "gxx_channel": None,
    "gxx_uncertainty": 1.0,
    "gyy_channel": None,
    "gyy_uncertainty": 1.0,
    "gzz_channel": None,
    "gzz_uncertainty": 1.0,
    "gxz_channel": None,
    "gxz_uncertainty": 1.0,
    "gyz_channel": None,
    "gyz_uncertainty": 1.0,
    "gx_channel": None,
    "gx_uncertainty": 1.0,
    "gy_channel": None,
    "gy_uncertainty": 1.0,
    "starting_model_object": None,
    "starting_model": 1e-4,
    "tile_spatial": 1,
    "output_tile_files": False,
    "z_from_topo": False,
    "receivers_radar_drape": None,
    "receivers_offset_x": 0.0,
    "receivers_offset_y": 0.0,
    "receivers_offset_z": 0.0,
    "gps_receivers_offset": None,
    "ignore_values": None,
    "resolution": None,
    "detrend_order": None,
    "detrend_type": None,
    "max_chunk_size": 128,
    "chunk_by_rows": True,
    "mesh": None,
    "u_cell_size": 25.0,
    "v_cell_size": 25.0,
    "w_cell_size": 25.0,
    "octree_levels_topo": [0, 0, 4, 4],
    "octree_levels_obs": [4, 4, 4, 4],
    "depth_core": 500.0,
    "max_distance": 5000.0,
    "horizontal_padding": 1000.0,
    "vertical_padding": 1000.0,
    "window_center_x": None,
    "window_center_y": None,
    "window_width": None,
    "window_height": None,
    "window_azimuth": None,
    "inversion_style": "voxel",
    "chi_factor": 1.0,
    "sens_wts_threshold": 0.0,
    "every_iteration_bool": False,
    "f_min_change": 1e-4,
    "minGNiter": 1,
    "beta_tol": 0.5,
    "prctile": 95,
    "coolingRate": 1,
    "coolEps_q": True,
    "coolEpsFact": 1.2,
    "beta_search": False,
    "starting_chi_factor": None,
    "max_iterations": 25,
    "max_line_search_iterations": 20,
    "max_cg_iterations": 30,
    "max_global_iterations": 100,
    "initial_beta_ratio": 10.0,
    "initial_beta": None,
    "tol_cg": 1e-4,
    "alpha_s": 1.0,
    "alpha_x": 1.0,
    "alpha_y": 1.0,
    "alpha_z": 1.0,
    "s_norm": 0.0,
    "x_norm": 2.0,
    "y_norm": 2.0,
    "z_norm": 2.0,
    "reference_model_object": None,
    "reference_model": 0.0,
    "gradient_type": "total",
    "lower_bound_object": None,
    "lower_bound": None,
    "upper_bound_object": None,
    "upper_bound": None,
    "parallelized": True,
    "n_cpu": None,
    "max_ram": None,
    "out_group": "GravityInversion",
    "monitoring_directory": None,
    "workspace_geoh5": None,
    "run_command": "geoapps.inversion.driver",
    "run_command_boolean": False,
    "conda_environment": "geoapps",
    "distributed_workers": None,
    "gz_channel_bool": False,
    "guv_channel_bool": False,
    "gxy_channel_bool": False,
    "gxx_channel_bool": False,
    "gyy_channel_bool": False,
    "gzz_channel_bool": False,
    "gxz_channel_bool": False,
    "gyz_channel_bool": False,
    "gx_channel_bool": False,
    "gy_channel_bool": False,
}
forward_defaults = {
    "title": "SimPEG gravity Forward",
    "inversion_type": "gravity",
    "geoh5": None,  # Must remain at top of list for notebook app initialization
    "forward_only": True,
    "topography_object": None,
    "topography": None,
    "data_object": None,
    "gz_channel_bool": False,
    "guv_channel_bool": False,
    "gxy_channel_bool": False,
    "gxx_channel_bool": False,
    "gyy_channel_bool": False,
    "gzz_channel_bool": False,
    "gxz_channel_bool": False,
    "gyz_channel_bool": False,
    "gx_channel_bool": False,
    "gy_channel_bool": False,
    "starting_model_object": None,
    "starting_model": None,
    "tile_spatial": 1,
    "output_tile_files": False,
    "z_from_topo": False,
    "receivers_radar_drape": None,
    "receivers_offset_x": 0.0,
    "receivers_offset_y": 0.0,
    "receivers_offset_z": 0.0,
    "gps_receivers_offset": None,
    "resolution": None,
    "max_chunk_size": 128,
    "chunk_by_rows": True,
    "mesh": None,
    "u_cell_size": 25.0,
    "v_cell_size": 25.0,
    "w_cell_size": 25.0,
    "octree_levels_topo": [0, 0, 4, 4],
    "octree_levels_obs": [4, 4, 4, 4],
    "depth_core": 500.0,
    "max_distance": 5000.0,
    "horizontal_padding": 1000.0,
    "vertical_padding": 1000.0,
    "window_center_x": None,
    "window_center_y": None,
    "window_width": None,
    "window_height": None,
    "window_azimuth": None,
    "parallelized": True,
    "n_cpu": None,
    "out_group": "GravityForward",
    "monitoring_directory": None,
    "workspace_geoh5": None,
    "run_command": "geoapps.inversion.driver",
    "run_command_boolean": False,
    "conda_environment": "geoapps",
    "distributed_workers": None,
    "gradient_type": "total",
    "alpha_s": 1.0,
    "alpha_x": 1.0,
    "alpha_y": 1.0,
    "alpha_z": 1.0,
    "s_norm": 0.0,
    "x_norm": 2.0,
    "y_norm": 2.0,
    "z_norm": 2.0,
}

inversion_ui_json = {
    "gz_channel_bool": False,
    "guv_channel_bool": False,
    "gxy_channel_bool": False,
    "gxx_channel_bool": False,
    "gyy_channel_bool": False,
    "gzz_channel_bool": False,
    "gxz_channel_bool": False,
    "gyz_channel_bool": False,
    "gx_channel_bool": False,
    "gy_channel_bool": False,
}

forward_ui_json = {
    "gradient_type": "total",
    "alpha_s": 1.0,
    "alpha_x": 1.0,
    "alpha_y": 1.0,
    "alpha_z": 1.0,
    "s_norm": 0.0,
    "x_norm": 2.0,
    "y_norm": 2.0,
    "z_norm": 2.0,
}

default_ui_json = {
    "title": "SimPEG gravity inversion",
    "inversion_type": "gravity",
    "gz_channel_bool": {
        "group": "Data",
        "main": True,
        "label": "Use Gz",
        "value": False,
    },
    "gz_channel": {
        "association": ["Cell", "Vertex"],
        "dataType": "Float",
        "group": "Data",
        "main": True,
        "label": "Gz channel",
        "parent": "data_object",
        "optional": True,
        "enabled": False,
        "value": None,
    },
    "gz_uncertainty": {
        "association": ["Cell", "Vertex"],
        "dataType": "Float",
        "group": "Data",
        "main": True,
        "isValue": True,
        "label": "Gz uncertainty (mGal)",
        "parent": "data_object",
        "dependency": "gz_channel",
        "dependencyType": "enabled",
        "property": None,
        "value": 1.0,
    },
    "guv_channel_bool": {
        "group": "Data",
        "main": True,
        "label": "Use Guv",
        "value": False,
    },
    "guv_channel": {
        "association": ["Cell", "Vertex"],
        "dataType": "Float",
        "group": "Data",
        "main": True,
        "label": "Guv channel",
        "parent": "data_object",
        "optional": True,
        "enabled": False,
        "value": None,
    },
    "guv_uncertainty": {
        "association": ["Cell", "Vertex"],
        "dataType": "Float",
        "group": "Data",
        "main": True,
        "isValue": True,
        "label": "Guv uncertainty (mGal)",
        "parent": "data_object",
        "dependency": "guv_channel",
        "dependencyType": "enabled",
        "property": None,
        "value": 1.0,
    },
    "gxy_channel_bool": {
        "group": "Data",
        "main": True,
        "label": "Use Gxy (Gne)",
        "value": False,
    },
    "gxy_channel": {
        "association": ["Cell", "Vertex"],
        "dataType": "Float",
        "group": "Data",
        "main": True,
        "label": "Gxy (Gne) channel",
        "parent": "data_object",
        "optional": True,
        "enabled": False,
        "value": None,
    },
    "gxy_uncertainty": {
        "association": ["Cell", "Vertex"],
        "dataType": "Float",
        "group": "Data",
        "main": True,
        "isValue": True,
        "label": "Gxy (Gne) uncertainty (mGal)",
        "parent": "data_object",
        "dependency": "gxy_channel",
        "dependencyType": "enabled",
        "property": None,
        "value": 1.0,
    },
    "gxx_channel_bool": {
        "group": "Data",
        "main": True,
        "label": "Use Gxx",
        "value": False,
    },
    "gxx_channel": {
        "association": ["Cell", "Vertex"],
        "dataType": "Float",
        "group": "Data",
        "main": True,
        "label": "Gxx channel",
        "parent": "data_object",
        "optional": True,
        "enabled": False,
        "value": None,
    },
    "gxx_uncertainty": {
        "association": ["Cell", "Vertex"],
        "dataType": "Float",
        "group": "Data",
        "main": True,
        "isValue": True,
        "label": "Gxx uncertainty (mGal)",
        "parent": "data_object",
        "dependency": "gxx_channel",
        "dependencyType": "enabled",
        "property": None,
        "value": 1.0,
    },
    "gyy_channel_bool": {
        "group": "Data",
        "main": True,
        "label": "Use Gyy",
        "value": False,
    },
    "gyy_channel": {
        "association": ["Cell", "Vertex"],
        "dataType": "Float",
        "group": "Data",
        "main": True,
        "label": "Gyy channel",
        "parent": "data_object",
        "optional": True,
        "enabled": False,
        "value": None,
    },
    "gyy_uncertainty": {
        "association": ["Cell", "Vertex"],
        "dataType": "Float",
        "group": "Data",
        "main": True,
        "isValue": True,
        "label": "Gyy uncertainty (mGal)",
        "parent": "data_object",
        "dependency": "gyy_channel",
        "dependencyType": "enabled",
        "property": None,
        "value": 1.0,
    },
    "gzz_channel_bool": {
        "group": "Data",
        "main": True,
        "label": "Use Gzz",
        "value": False,
    },
    "gzz_channel": {
        "association": ["Cell", "Vertex"],
        "dataType": "Float",
        "group": "Data",
        "main": True,
        "label": "Gzz channel",
        "parent": "data_object",
        "optional": True,
        "enabled": False,
        "value": None,
    },
    "gzz_uncertainty": {
        "association": ["Cell", "Vertex"],
        "dataType": "Float",
        "group": "Data",
        "main": True,
        "isValue": True,
        "label": "Gzz uncertainty (mGal)",
        "parent": "data_object",
        "dependency": "gzz_channel",
        "dependencyType": "enabled",
        "property": None,
        "value": 1.0,
    },
    "gxz_channel_bool": {
        "group": "Data",
        "main": True,
        "label": "Use Gxz",
        "value": False,
    },
    "gxz_channel": {
        "association": ["Cell", "Vertex"],
        "dataType": "Float",
        "group": "Data",
        "main": True,
        "label": "Gxz channel",
        "parent": "data_object",
        "optional": True,
        "enabled": False,
        "value": None,
    },
    "gxz_uncertainty": {
        "association": ["Cell", "Vertex"],
        "dataType": "Float",
        "group": "Data",
        "main": True,
        "isValue": True,
        "label": "Gxz uncertainty (mGal)",
        "parent": "data_object",
        "dependency": "gxz_channel",
        "dependencyType": "enabled",
        "property": None,
        "value": 1.0,
    },
    "gyz_channel_bool": {
        "group": "Data",
        "main": True,
        "label": "Use Gyz",
        "value": False,
    },
    "gyz_channel": {
        "association": ["Cell", "Vertex"],
        "dataType": "Float",
        "group": "Data",
        "main": True,
        "label": "Gyz channel",
        "parent": "data_object",
        "optional": True,
        "enabled": False,
        "value": None,
    },
    "gyz_uncertainty": {
        "association": ["Cell", "Vertex"],
        "dataType": "Float",
        "group": "Data",
        "main": True,
        "isValue": True,
        "label": "Gyz uncertainty (mGal)",
        "parent": "data_object",
        "dependency": "gyz_channel",
        "dependencyType": "enabled",
        "property": None,
        "value": 1.0,
    },
    "gx_channel_bool": {
        "group": "Data",
        "main": True,
        "label": "Use Gx",
        "value": False,
    },
    "gx_channel": {
        "association": ["Cell", "Vertex"],
        "dataType": "Float",
        "group": "Data",
        "main": True,
        "label": "Gx channel",
        "parent": "data_object",
        "optional": True,
        "enabled": False,
        "value": None,
    },
    "gx_uncertainty": {
        "association": ["Cell", "Vertex"],
        "dataType": "Float",
        "group": "Data",
        "main": True,
        "isValue": True,
        "label": "Gx uncertainty (mGal)",
        "parent": "data_object",
        "dependency": "gx_channel",
        "dependencyType": "enabled",
        "property": None,
        "value": 1.0,
    },
    "gy_channel_bool": {
        "group": "Data",
        "main": True,
        "label": "Use Gy",
        "value": False,
    },
    "gy_channel": {
        "association": ["Cell", "Vertex"],
        "dataType": "Float",
        "group": "Data",
        "main": True,
        "label": "Gy channel",
        "parent": "data_object",
        "optional": True,
        "enabled": False,
        "value": None,
    },
    "gy_uncertainty": {
        "association": ["Cell", "Vertex"],
        "dataType": "Float",
        "group": "Data",
        "main": True,
        "isValue": True,
        "label": "Gy uncertainty (mGal)",
        "parent": "data_object",
        "dependency": "gy_channel",
        "dependencyType": "enabled",
        "property": None,
        "value": 1.0,
    },
    "starting_model": {
        "association": ["Cell", "Vertex"],
        "dataType": "Float",
        "group": "Starting Model",
        "main": True,
        "isValue": True,
        "parent": "starting_model_object",
        "label": "Density (g/cc)",
        "property": None,
        "value": 0.0,
    },
    "out_group": {"label": "Results group name", "value": "gravity"},
}

default_ui_json = dict(base_default_ui_json, **default_ui_json)

################ Validations #################


validations = {
    "inversion_type": {
        "required": True,
        "values": ["gravity"],
    },
    "data_object": {"types": [str, UUID, Points, Surface, Grid2D]},
    "gz_channel": {"one_of": "data channel"},
    "gz_uncertainty": {"one_of": "uncertainty channel"},
    "guv_channel": {"one_of": "data channel"},
    "guv_uncertainty": {"one_of": "uncertainty channel"},
    "gxy_channel": {"one_of": "data channel"},
    "gxy_uncertainty": {"one_of": "uncertainty channel"},
    "gxx_channel": {"one_of": "data channel"},
    "gxx_uncertainty": {"one_of": "uncertainty channel"},
    "gyy_channel": {"one_of": "data channel"},
    "gyy_uncertainty": {"one_of": "uncertainty channel"},
    "gzz_channel": {"one_of": "data channel"},
    "gzz_uncertainty": {"one_of": "uncertainty channel"},
    "gxz_channel": {"one_of": "data channel"},
    "gxz_uncertainty": {"one_of": "uncertainty channel"},
    "gyz_channel": {"one_of": "data channel"},
    "gyz_uncertainty": {"one_of": "uncertainty channel"},
    "gx_channel": {"one_of": "data channel"},
    "gx_uncertainty": {"one_of": "uncertainty channel"},
    "gy_channel": {"one_of": "data channel"},
    "gy_uncertainty": {"one_of": "uncertainty channel"},
}

app_initializer = {
    "geoh5": "../../../assets/FlinFlon.geoh5",
    "forward_only": False,
    "data_object": UUID("{538a7eb1-2218-4bec-98cc-0a759aa0ef4f}"),
    "gz_channel": UUID("{6de9177a-8277-4e17-b76c-2b8b05dcf23c}"),
    "gz_uncertainty": 0.05,
    "u_cell_size": 25.0,
    "v_cell_size": 25.0,
    "w_cell_size": 25.0,
    "resolution": 50.0,
    "octree_levels_topo": [0, 0, 4, 4],
    "octree_levels_obs": [4, 4, 4, 4],
    "depth_core": 1200.0,
    "horizontal_padding": 1000.0,
    "vertical_padding": 1000.0,
    "window_center_x": 314155.0,
    "window_center_y": 6071000.0,
    "window_width": 1000.0,
    "window_height": 1000.0,
    "window_azimuth": 0.0,
    "s_norm": 0.0,
    "x_norm": 2.0,
    "y_norm": 2.0,
    "z_norm": 2.0,
    "starting_model": 1e-4,
    "max_iterations": 25,
    "topography_object": UUID("{ab3c2083-6ea8-4d31-9230-7aad3ec09525}"),
    "topography": UUID("{a603a762-f6cb-4b21-afda-3160e725bf7d}"),
    "z_from_topo": True,
    "out_group": "GravityInversion",
}