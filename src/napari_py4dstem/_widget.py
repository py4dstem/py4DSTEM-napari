"""
py4DSTEM widget module
"""

import py4D_browser
from magicgui.widgets import create_widget
from napari import Viewer
from napari.layers.image import Image
from napari.layers.shapes import Shapes
from napari.layers.points import Points
from napari.utils.events import Event
from qtpy.QtCore import QEvent, QObject
from qtpy.QtWidgets import QPushButton, QVBoxLayout, QWidget


class py4DSTEM(QWidget):
    # your QWidget.__init__ can optionally request the napari viewer instance
    # use a type annotation of 'napari.viewer.Viewer' for any parameter
    def __init__(self, viewer: Viewer):
        super().__init__()
        self.viewer = viewer

        viewer.dims.events.ndim.connect(self.my_callback)
        viewer.layers.events.inserted.connect(
            self.added_layer_changed_callback
        )
        viewer.layers.events.removed.connect(
            self.removed_layer_changed_callback
        )
        viewer.layers.events.moved.connect(self.moved_layer_changed_callback)
        viewer.layers.events.reordered.connect(
            self.reordered_layer_changed_callback
        )

        viewer.dims.events.current_step.connect(self.step_callback)

        self.setLayout(QVBoxLayout())

        btn = QPushButton("Hide/Show")
        btn.clicked.connect(self._on_click)

        self.win = py4D_browser.DataViewer([])
        self.win.diffraction_space_widget.hide()

        self.win.real_space_point_selector.sigRegionChanged.connect(
            self.roi_changed
        )
        self._image_layer_combo = create_widget(
            label="Image", annotation=Image
        )

        print(btn)
        self.layout().addWidget(self._image_layer_combo.native)
        self.layout().addWidget(btn)
        self.layout().addWidget(self.win)

        print(self._image_layer_combo.native)

        self.installEventFilter(self)

    def roi_changed(self, object=None, event=None):
        self.viewer.layers[0].data = self.win.diffraction_space_widget.image

    def added_layer_changed_callback(self, event: Event):
        # print("add Layer changed", event.value, event.value.metadata)
        metadata = event.value.metadata

        if isinstance(event.value, Image) and "datacube" in metadata:
            datacube = metadata["datacube"]
            filepath = metadata["filepath"]

            self.win.datacube = datacube

            self.win.diffraction_scale_bar.pixel_size = (
                datacube.calibration.get_Q_pixel_size()
            )
            self.win.diffraction_scale_bar.units = (
                datacube.calibration.get_Q_pixel_units()
            )

            self.win.real_space_scale_bar.pixel_size = (
                datacube.calibration.get_R_pixel_size()
            )
            self.win.real_space_scale_bar.units = (
                datacube.calibration.get_R_pixel_units()
            )

            self.win.fft_scale_bar.pixel_size = (
                1.0 / datacube.calibration.get_R_pixel_size() / datacube.R_Ny
            )
            self.win.fft_scale_bar.units = (
                f"1/{datacube.calibration.get_R_pixel_units()}"
            )

            self.win.update_diffraction_space_view(reset=True)
            self.win.update_real_space_view(reset=True)
            self.win.setWindowTitle(filepath)

            self.viewer.layers[0].data = (
                self.win.diffraction_space_widget.image
            )

        if isinstance(event.value, Points):
            print("detected points inserted", event.value)
            point: Points = event.value
            point.events.set_data.connect(self.points_changed)

        if isinstance(event.value, Shapes):
            shape: Shapes = event.value
            shape.events.set_data.connect(self.shape_changed)

    def points_changed(self, event: Event):
        print("detecting points changed", event.source)
        points: Points = event.source
        points_array = points.data

        if len(points_array) > 0 and len(points_array[0]) == 2:
            self.win.update_real_space_view()
            print(points_array[0])
            self.win.virtual_detector_point.setPos(points_array[0])

    """
    Other interesting callbacks
    """

    def shape_changed(self, event: Event):
        print("detecting shape changed", event.source)

    def my_callback(self, event: Event):
        print("The number of dims shown is now:", event.value)

    def step_callback(self, event: Event):
        print("The current steps shown is now:", event.value)

    def removed_layer_changed_callback(self, event: Event):
        print("remove Layer changed", event.value)

    def moved_layer_changed_callback(self, event: Event):
        print("moved Layer changed", event.value)

    def reordered_layer_changed_callback(event: Event):
        print("reorder Layer changed", event.value)

    def eventFilter(self, obj: QObject, event: QEvent):
        # print("event filter")
        if event.type() == QEvent.ParentChange:
            self._image_layer_combo.parent_changed.emit(self.parent())

        return super().eventFilter(obj, event)

    def _on_click(self):
        print("napari has", len(self.viewer.layers), "layers")
        print(self.viewer.layers)

        if self.win.diffraction_space_widget.isVisible():
            self.win.diffraction_space_widget.hide()
        else:
            self.win.diffraction_space_widget.show()
