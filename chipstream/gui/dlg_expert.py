from collections.abc import Callable

from PyQt6 import QtWidgets

#: pipeline steps with expert keyword arguments (key, label)
EXPERT_STEPS = [
    ("background", "Background computation (sparsemed)"),
    ("segmentation", "Segmentation"),
    ("feature", "Feature extraction"),
    ("gate", "Gating"),
]


def lines_to_kwargs(text: str) -> list[str]:
    """Convert multi-line text to a list of `KEY=VALUE` strings

    Empty lines and lines starting with "#" are ignored.
    """
    args = []
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            args.append(line)
    return args


class ExpertSettingsDialog(QtWidgets.QDialog):
    def __init__(self,
                 parent,
                 expert_kwargs: dict[str, list[str]],
                 validator: Callable[[dict[str, list[str]]], None]):
        """Dialog for editing additional keyword arguments

        Parameters
        ----------
        parent:
            parent widget
        expert_kwargs:
            current keyword arguments for each step in `EXPERT_STEPS`,
            as lists of `KEY=VALUE` strings
        validator:
            called with the new keyword arguments when the user clicks
            OK; raises `ValueError` if they are invalid
        """
        super().__init__(parent)
        self.setWindowTitle("Expert settings")
        self.validator = validator
        layout = QtWidgets.QVBoxLayout(self)
        info = QtWidgets.QLabel(
            "Additional keyword arguments for the pipeline steps, one "
            "<tt>KEY=VALUE</tt> per line. They override the settings in "
            "the main window and change the pipeline identifiers. The "
            "available keyword arguments are listed in "
            "<tt>chipstream-cli --help</tt>. Only change these settings "
            "if you know what you are doing.")
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QtWidgets.QFormLayout()
        self.edits = {}
        for key, label in EXPERT_STEPS:
            edit = QtWidgets.QPlainTextEdit(self)
            edit.setPlaceholderText("KEY=VALUE")
            edit.setPlainText("\n".join(expert_kwargs.get(key, [])))
            edit.setMaximumHeight(80)
            form.addRow(label, edit)
            self.edits[key] = edit
        layout.addLayout(form)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
            | QtWidgets.QDialogButtonBox.StandardButton.Reset)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        btn_reset = buttons.button(
            QtWidgets.QDialogButtonBox.StandardButton.Reset)
        if btn_reset is not None:
            btn_reset.clicked.connect(self.on_reset)
        layout.addWidget(buttons)
        self.resize(600, 450)

    def get_expert_kwargs(self) -> dict[str, list[str]]:
        """Return the keyword arguments entered by the user"""
        return {key: lines_to_kwargs(edit.toPlainText())
                for key, edit in self.edits.items()}

    def accept(self):
        """Validate the keyword arguments before closing the dialog"""
        try:
            self.validator(self.get_expert_kwargs())
        except ValueError as e:
            QtWidgets.QMessageBox.warning(self, "Invalid expert settings",
                                          str(e))
        else:
            super().accept()

    def on_reset(self):
        """Remove all keyword arguments"""
        for edit in self.edits.values():
            edit.clear()
