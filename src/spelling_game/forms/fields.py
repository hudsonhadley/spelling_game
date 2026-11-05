"""Reusable normalization for account fields."""

from wtforms import EmailField


class NormalizedEmailField(EmailField):
    """Trim and lowercase email addresses consistently for storage and lookup."""

    def process_formdata(self, valuelist):
        super().process_formdata(valuelist)
        if self.data:
            self.data = self.data.strip().lower()
