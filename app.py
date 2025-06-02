import sys
import os
import math
import pandas as pd
import numpy as np
import trimesh
import pyvista as pv
from pyvistaqt import QtInteractor

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QFileDialog,
    QPushButton, QComboBox, QLabel, QVBoxLayout, QWidget, QMessageBox
)

class PackAssistantApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PackAssistant")
        self.resize(1000, 600)

        # State
        self.boxes = pd.DataFrame()
        self.selected_box = None
        self.part_mesh = None

        # UI Elements
        central = QWidget()
        self.setCentralWidget(central)
        vlay = QVBoxLayout(central)

        # ComboBox for box selection
        self.box_combo = QComboBox()
        self.box_combo.currentIndexChanged.connect(self.on_box_change)
        vlay.addWidget(QLabel("Select box:"))
        vlay.addWidget(self.box_combo)

        # Buttons
        btn_load_csv = QPushButton("Load boxes.csv")
        btn_load_csv.clicked.connect(self.load_boxes_csv)
        vlay.addWidget(btn_load_csv)

        btn_load_part = QPushButton("Load STEP part")
        btn_load_part.clicked.connect(self.load_part)
        vlay.addWidget(btn_load_part)

        btn_compute = QPushButton("Compute & Visualize")
        btn_compute.clicked.connect(self.compute_and_show)
        vlay.addWidget(btn_compute)

        self.result_label = QLabel("Pieces fit: n/a")
        vlay.addWidget(self.result_label)

        # 3D viewport
        self.plotter = QtInteractor(self)
        vlay.addWidget(self.plotter.interactor)

    def load_boxes_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open boxes.csv", filter="CSV files (*.csv)")
        if not path:
            return
        try:
            df = pd.read_csv(path)
            # Expect columns: name,width,height,depth (units: mm or same)
            for c in ("name", "width", "height", "depth"):
                if c not in df.columns:
                    raise ValueError(f"Missing column {c}")
            self.boxes = df
            self.box_combo.clear()
            self.box_combo.addItems(df["name"].tolist())
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load CSV:\n{e}")

    def on_box_change(self, idx):
        if idx < 0 or self.boxes.empty:
            self.selected_box = None
            return
        row = self.boxes.iloc[idx]
        self.selected_box = {
            "name": row["name"],
            "dims": np.array([row["width"], row["height"], row["depth"]], dtype=float)
        }

    def load_part(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open STEP file", filter="STEP files (*.step *.stp)")
        if not path:
            return
        try:
            mesh = trimesh.load(path, force='mesh')
            if mesh.is_empty:
                raise ValueError("Empty mesh")
            self.part_mesh = mesh
            QMessageBox.information(self, "Part loaded", f"Loaded part. Bounding box extents: {mesh.extents}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load STEP:\n{e}")

    def compute_and_show(self):
        if self.selected_box is None:
            QMessageBox.warning(self, "Warning", "Please select a box.")
            return
        if self.part_mesh is None:
            QMessageBox.warning(self, "Warning", "Please load a part STEP file.")
            return

        # Compute how many fit along each axis
        part_dims = self.part_mesh.extents
        box_dims = self.selected_box["dims"]
        counts = np.floor(box_dims / part_dims).astype(int)
        total = int(counts.prod())
        self.result_label.setText(f"Pieces fit: {total} ({counts[0]} x {counts[1]} x {counts[2]})")

        # Generate part positions
        coords = []
        for i in range(counts[0]):
            for j in range(counts[1]):
                for k in range(counts[2]):
                    coords.append((i*part_dims[0], j*part_dims[1], k*part_dims[2]))

        # Visualize
        self.plotter.clear()
        # draw box
        box = pv.Box(bounds=(0, box_dims[0], 0, box_dims[1], 0, box_dims[2]))
        self.plotter.add_mesh(box, style='wireframe', color='black', line_width=2)

        # draw parts
        part_pv = pv.wrap(self.part_mesh.vertices)
        # Note: pv.wrap on trimesh works for points only; better convert trimesh to pyvista
        tri = pv.PolyData(self.part_mesh.vertices, np.hstack(self.part_mesh.faces + np.arange(0, len(self.part_mesh.vertices)).reshape(-1,1)))
        for c in coords:
            trans = tri.copy().translate(c)
            self.plotter.add_mesh(trans, color="orange", opacity=1.0)

        self.plotter.reset_camera()
        self.plotter.render()

def main():
    app = QApplication(sys.argv)
    win = PackAssistantApp()
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()