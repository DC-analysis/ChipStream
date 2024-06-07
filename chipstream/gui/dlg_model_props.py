import hashlib
from importlib import resources
import pathlib

from PyQt6 import uic, QtWidgets


class TorchModelProperties(QtWidgets.QDialog):
    def __init__(self, parent, model_file, *args, **kwargs):
        QtWidgets.QWidget.__init__(self, parent, *args, **kwargs)
        ref_ui = resources.files("chipstream.gui") / "dlg_model_props.ui"
        with resources.as_file(ref_ui) as path_ui:
            uic.loadUi(path_ui, self)

        model_file = pathlib.Path(model_file)

        # load the model
        from dcnum.segm.segm_torch.torch_model import load_model
        _, metadata = load_model(model_file, "cpu")
        md5sum = hashlib.md5(model_file.read_bytes()).hexdigest()

        self.lineEdit_name.setText(metadata["name"])
        self.lineEdit_path.setText(str(model_file.resolve()))
        self.lineEdit_id.setText(metadata["identifier"] + "_" + md5sum[:5])
        self.lineEdit_date.setText(metadata["date"])
        self.lineEdit_hash.setText(md5sum)

        preproc = ", ".join(
            [f"{k}={v}" for k, v in metadata["preprocessing"].items()])
        self.lineEdit_params.setText(preproc)
        self.plainTextEdit_descr.setPlainText(metadata["description"])
