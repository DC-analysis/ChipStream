import hashlib
import pathlib

from PyQt6 import QtWidgets

from .dlg_model_props_ui import Ui_Dialog


class TorchModelProperties(QtWidgets.QDialog):
    def __init__(self, parent, model_file, *args, **kwargs):
        QtWidgets.QWidget.__init__(self, parent, *args, **kwargs)

        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

        model_file = pathlib.Path(model_file)

        # load the model
        from dcnum.segm.segm_torch.torch_model import get_model_meta

        try:
            metadata = get_model_meta(model_file, device="cpu")
            md5sum = hashlib.md5(model_file.read_bytes()).hexdigest()

            self.ui.lineEdit_name.setText(metadata["name"])
            self.ui.lineEdit_path.setText(str(model_file.resolve()))
            self.ui.lineEdit_id.setText(metadata["identifier"] + "_" + md5sum[:5])
            self.ui.lineEdit_date.setText(metadata["date"])
            self.ui.lineEdit_hash.setText(md5sum)

            preproc = ", ".join(
                [f"{k}={v}" for k, v in metadata["preprocessing"].items()])
            self.ui.lineEdit_params.setText(preproc)
            self.ui.plainTextEdit_descr.setPlainText(metadata["description"])
        except BaseException:
            raise ValueError(
                f"Failed to fetch model metadata for '{model_file}'")
