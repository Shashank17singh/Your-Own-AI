from tkinter.commondialog import Dialog

__all__ = ["Chooser", "askcolor"]


class Chooser(Dialog):
    """Create a dialog for the tk_chooseColor command.
    Args:
        master: The master widget for this dialog.  If not provided,
            defaults to options['parent'] (if defined).
        options: Dictionary of options for the tk_chooseColor call.
            initialcolor: Specifies the selected color when the
                dialog is first displayed.  This can be a tk color
                string or a 3-tuple of ints in the range (0, 255)
                for an RGB triplet.
            parent: The parent window of the color dialog.  The
                color dialog is displayed on top of this.
            title: A string for the title of the dialog box.
    """

    command = "tk_chooseColor"

    def _fixoptions(self):
        """Ensure initialcolor is a tk color string.
        Convert initialcolor from a RGB triplet to a color string.
        """
        try:
            color = self.options["initialcolor"]
            if isinstance(color, tuple):
                self.options["initialcolor"] = "#%02x%02x%02x" % color
        except KeyError:
            pass

    def _fixresult(self, widget, result):
        """Adjust result returned from call to tk_chooseColor.
        Return both an RGB tuple of ints in the range (0, 255) and the
        tk color string in the form #rrggbb.
        """
        if not result or not str(result):
            return None, None  # canceled
        r, g, b = widget.winfo_rgb(result)
        return (r // 256, g // 256, b // 256), str(result)


def askcolor(color=None, **options):
    """Display dialog window for selection of a color.
    Convenience wrapper for the Chooser class.  Displays the color
    chooser dialog with color as the initial value.
    """
    if color:
        options = options.copy()
        options["initialcolor"] = color
    return Chooser(**options).show()


if __name__ == "__main__":
    print("color", askcolor())
