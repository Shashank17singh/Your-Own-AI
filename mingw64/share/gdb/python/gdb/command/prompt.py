"""GDB command for working with extended prompts."""

import gdb
import gdb.prompt


class _ExtendedPrompt(gdb.Parameter):
    """Set the extended prompt.
    Usage: set extended-prompt VALUE
    Substitutions are applied to VALUE to compute the real prompt.
    The currently defined substitutions are:"""

    __doc__ = __doc__ + "\n" + gdb.prompt.prompt_help()
    set_doc = "Set the extended prompt."
    show_doc = "Show the extended prompt."

    def __init__(self):
        super(_ExtendedPrompt, self).__init__(
            "extended-prompt", gdb.COMMAND_SUPPORT, gdb.PARAM_STRING_NOESCAPE
        )
        self.value = ""
        self.hook_set = False

    def get_show_string(self, pvalue):
        if self.value:
            return "The extended prompt is: " + self.value
        else:
            return "The extended prompt is not set."

    def get_set_string(self):
        if self.hook_set is False:
            gdb.prompt_hook = self.before_prompt_hook
            self.hook_set = True
        return ""

    def before_prompt_hook(self, current):
        if self.value:
            return gdb.prompt.substitute_prompt(self.value)
        else:
            return None


_ExtendedPrompt()
