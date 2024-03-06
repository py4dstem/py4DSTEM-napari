"""
This module is an example of a barebones numpy reader plugin for napari.

It implements the Reader specification, but your plugin may choose to
implement multiple readers or even other plugin contributions. see:
https://napari.org/stable/plugins/guides.html?#readers
"""

import os

import h5py
import numpy as np
import py4DSTEM


# Helper function code to read py4DSTEM data
##############


def find_calibrations(dset: h5py.Dataset):
    # Attempt to find calibrations from an H5 file
    R_size, R_units, Q_size, Q_units = 1.0, "pixels", 1.0, "pixels"

    # Does it look like a py4DSTEM file?
    try:
        if "emd_group_type" in dset.parent.attrs:
            # EMD files theoretically store this in the Array,
            # but in practice seem to only keep the calibrations
            # in the Metadata object, which is separate

            # R_size = dset.parent["dim0"][1] - dset.parent["dim0"][0]
            # R_units = dset.parent["dim0"].attrs["units"]

            # Q_size = dset.parent["dim3"][1] - dset.parent["dim3"][0]
            # Q_units = dset.parent["dim3"].attrs["units"]
            R_size = dset.parent.parent["metadatabundle"]["calibration"][
                "R_pixel_size"
            ][()]
            R_units = dset.parent.parent["metadatabundle"]["calibration"][
                "R_pixel_units"
            ][()].decode()

            Q_size = dset.parent.parent["metadatabundle"]["calibration"][
                "Q_pixel_size"
            ][()]
            Q_units = dset.parent.parent["metadatabundle"]["calibration"][
                "Q_pixel_units"
            ][()].decode()
    except Exception as e:
        print(
            "This file looked like a py4DSTEM dataset but the dim vectors appear malformed..."
        )
        print(repr(e))

    # Does it look like an abTEM file?
    try:
        if "sampling" in dset.parent and "units" in dset.parent:
            R_size = dset.parent["sampling"][0]
            R_units = dset.parent["units"][0].decode()

            Q_size = dset.parent["sampling"][3]
            Q_units = dset.parent["units"][3].decode()
    except Exception as e:
        print(
            "This file looked like an abTEM simulation but the calibrations aren't as expected..."
        )
        print(repr(e))

    return R_size, R_units, Q_size, Q_units


def get_4D(f, datacubes=None):
    if datacubes is None:
        datacubes = []
    for k in f.keys():
        if isinstance(f[k], h5py.Dataset):
            # we found data
            if len(f[k].shape) == 4:
                datacubes.append(f[k])
        elif isinstance(f[k], h5py.Group):
            get_4D(f[k], datacubes)
    return datacubes


def load_file(filepath, mmap=False, binning=1):
    print(f"Loading file {filepath}")
    extension = os.path.splitext(filepath)[-1].lower()
    print(f"Type: {extension}")

    if extension in (".h5", ".hdf5", ".py4dstem", ".emd"):
        datacubes = get_4D(h5py.File(filepath, "r"))
        print(f"Found {len(datacubes)} 4D datasets inside the HDF5 file...")
        if len(datacubes) >= 1:
            # Read the first datacube in the HDF5 file into RAM
            print(f"Reading dataset at location {datacubes[0].name}")
            datacube = py4DSTEM.DataCube(
                datacubes[0] if mmap else datacubes[0][()]
            )

            R_size, R_units, Q_size, Q_units = find_calibrations(datacubes[0])

            datacube.calibration.set_R_pixel_size(R_size)
            datacube.calibration.set_R_pixel_units(R_units)
            datacube.calibration.set_Q_pixel_size(Q_size)
            datacube.calibration.set_Q_pixel_units(Q_units)

        else:
            raise ValueError("No 4D data detected in the H5 file!")
    elif extension in [".npy"]:
        datacube = py4DSTEM.DataCube(np.load(filepath))
    else:
        datacube = py4DSTEM.import_file(
            filepath,
            mem="MEMMAP" if mmap else "RAM",
            binfactor=binning,
        )

    return datacube


#############


def napari_get_reader(path):
    """A basic implementation of a Reader contribution.

    Parameters
    ----------
    path : str or list of str
        Path to file, or list of paths.

    Returns
    -------
    function or None
        If the path is a recognized format, return a function that accepts the
        same path or list of paths, and returns a list of layer data tuples.
    """
    if isinstance(path, list):
        path = path[0]

    # otherwise we return the *function* that can read ``path``.
    return reader_function


def reader_function(path):
    """Take a path or list of paths and return a list of LayerData tuples.

    Readers are expected to return data as a list of tuples, where each tuple
    is (data, [add_kwargs, [layer_type]]), "add_kwargs" and "layer_type" are
    both optional.

    Parameters
    ----------
    path : str or list of str
        Path to file, or list of paths.

    Returns
    -------
    layer_data : list of tuples
        A list of LayerData tuples where each tuple in the list contains
        (data, metadata, layer_type), where data is a numpy array, metadata is
        a dict of keyword arguments for the corresponding viewer.add_* method
        in napari, and layer_type is a lower-case string naming the type of
        layer. Both "meta", and "layer_type" are optional. napari will
        default to layer_type=="image" if not provided
    """

    path = path[0] if isinstance(path, list) else path

    add_kwargs = {}

    layer_type = "image"  # optional, default is "image"

    data_cube = load_file(path)

    # data = data_cube.data.metadata = {"datacube" : data_cube}

    add_kwargs = {"metadata": {"datacube": data_cube, "filepath": path}}
    return [(data_cube.data, add_kwargs, layer_type)]
