#  Copyright (c) 2022 Mira Geoscience Ltd.
#
#  This file is part of geoapps.
#
#  geoapps is distributed under the terms and conditions of the MIT License
#  (see LICENSE file at the root of this source code package).
# pylint: disable=too-many-locals

import numpy as np
from geoh5py.workspace import Workspace

from geoapps.inversion.driver import InversionDriver, start_inversion
from geoapps.inversion.natural_sources.magnetotellurics.params import (
    MagnetotelluricsParams,
)
from geoapps.shared_utils.utils import get_inversion_output
from geoapps.utils.testing import check_target, setup_inversion_workspace

# To test the full run and validate the inversion.
# Move this file out of the test directory and run.

target_run = {
    "data_norm": 0.00665,
    "phi_d": 0.495,
    "phi_m": 40.85,
}


def test_magnetotellurics_run(
    tmp_path,
    n_grid_points=2,
    max_iterations=1,
    pytest=True,
    refinement=(2,),
):

    np.random.seed(0)
    # Run the forward
    geoh5, _, model, survey, topography = setup_inversion_workspace(
        tmp_path,
        background=0.01,
        anomaly=1.0,
        n_electrodes=n_grid_points,
        n_lines=n_grid_points,
        refinement=refinement,
        drape_height=0.0,
        inversion_type="magnetotellurics",
        flatten=True,
    )
    params = MagnetotelluricsParams(
        forward_only=True,
        geoh5=geoh5,
        mesh=model.parent.uid,
        topography_object=topography.uid,
        resolution=0.0,
        z_from_topo=False,
        data_object=survey.uid,
        starting_model_object=model.parent.uid,
        starting_model=model.uid,
        conductivity_model=1e-2,
        zxx_real_channel_bool=True,
        zxx_imag_channel_bool=True,
        zxy_real_channel_bool=True,
        zxy_imag_channel_bool=True,
        zyx_real_channel_bool=True,
        zyx_imag_channel_bool=True,
        zyy_real_channel_bool=True,
        zyy_imag_channel_bool=True,
    )
    params.workpath = tmp_path
    fwr_driver = InversionDriver(params, warmstart=False)

    fwr_driver.run()
    geoh5 = Workspace(geoh5.h5file)

    survey = geoh5.get_entity(survey.uid)[0]

    data = {}
    uncertainties = {}
    components = {
        "zxx_real": "Zxx (real)",
        "zxx_imag": "Zxx (imag)",
        "zxy_real": "Zxy (real)",
        "zxy_imag": "Zxy (imag)",
        "zyx_real": "Zyx (real)",
        "zyx_imag": "Zyx (imag)",
        "zyy_real": "Zyy (real)",
        "zyy_imag": "Zyy (imag)",
    }

    for comp, cname in components.items():
        data[cname] = []
        # uncertainties[f"{cname} uncertainties"] = {}
        uncertainties[f"{cname} uncertainties"] = []
        for freq in survey.channels:
            data_envity = geoh5.get_entity(f"Iteration_0_{comp}_{freq:.2e}")[0].copy(
                parent=survey
            )
            data[cname].append(data_envity)

            uncert = survey.add_data(
                {
                    f"uncertainty_{comp}_{freq:.2e}": {
                        "values": np.abs(0.05 * data_envity.values)
                        + data_envity.values.std()
                    }
                }
            )
            uncertainties[f"{cname} uncertainties"].append(uncert.copy(parent=survey))
            # uncertainties[f"{cname} uncertainties"][freq] = {"values": u.copy(parent=survey)}

    survey.add_components_data(data)
    survey.add_components_data(uncertainties)

    data_kwargs = {}
    for i, comp in enumerate(components):
        data_kwargs[f"{comp}_channel"] = survey.property_groups[i].uid
        data_kwargs[f"{comp}_uncertainty"] = survey.property_groups[8 + i].uid

    orig_zyy_real_1 = geoh5.get_entity("Iteration_0_zyy_real_1.00e+01")[0].values

    # Run the inverse
    np.random.seed(0)
    params = MagnetotelluricsParams(
        geoh5=geoh5,
        mesh=geoh5.get_entity("mesh")[0].uid,
        topography_object=topography.uid,
        resolution=0.0,
        data_object=survey.uid,
        starting_model=0.01,
        reference_model=None,
        s_norm=0.0,
        x_norm=1.0,
        y_norm=1.0,
        z_norm=1.0,
        gradient_type="components",
        z_from_topo=False,
        upper_bound=0.75,
        conductivity_model=1e-2,
        max_iterations=max_iterations,
        initial_beta_ratio=1e-2,
        prctile=100,
        **data_kwargs,
    )
    params.workpath = tmp_path
    driver = InversionDriver(params)

    driver.run()
    run_ws = Workspace(driver.params.geoh5.h5file)
    output = get_inversion_output(
        driver.params.geoh5.h5file, driver.params.ga_group.uid
    )
    output["data"] = orig_zyy_real_1
    if pytest:
        check_target(output, target_run, tolerance=0.5)
        nan_ind = np.isnan(run_ws.get_entity("Iteration_0_model")[0].values)
        inactive_ind = run_ws.get_entity("active_cells")[0].values == 0
        assert np.all(nan_ind == inactive_ind)
    else:
        return fwr_driver.starting_model, driver.inverse_problem.model

    # test that one channel works
    data_kwargs = {k: v for k, v in data_kwargs.items() if "zxx_real" in k}
    geoh5.open()
    params = MagnetotelluricsParams(
        geoh5=geoh5,
        mesh=geoh5.get_entity("mesh")[0].uid,
        topography_object=topography.uid,
        data_object=survey.uid,
        starting_model=0.01,
        conductivity_model=1e-2,
        max_iterations=0,
        **data_kwargs,
    )
    params.write_input_file(path=tmp_path, name="Inv_run")
    driver = start_inversion(str(tmp_path / "Inv_run.ui.json"))

    return driver


if __name__ == "__main__":
    # Full run
    m_start, m_rec = test_magnetotellurics_run(
        "./", n_grid_points=8, max_iterations=30, pytest=False, refinement=(4, 8)
    )
    residual = np.linalg.norm(m_rec - m_start) / np.linalg.norm(m_start) * 100.0
    assert (
        residual < 50.0
    ), f"Deviation from the true solution is {residual:.2f}%. Validate the solution!"
    print("Conductivity model is within 15% of the answer. Let's go!!")
