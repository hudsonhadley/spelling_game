"""Flask-WTF forms for login and account creation."""

from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, InputRequired, Length

from .fields import NormalizedEmailField
from .validators import strong_password, valid_email


class LoginForm(FlaskForm):
    email = NormalizedEmailField("Email address", validators=[DataRequired(), Length(max=254), valid_email])
    password = PasswordField("Password", validators=[InputRequired(), Length(max=128)])
    remember = BooleanField("Remember me")
    submit = SubmitField("Log in")


class SignupForm(FlaskForm):
    name = StringField("Name", filters=[lambda value: value.strip() if value else value], validators=[DataRequired(), Length(max=80)])
    email = NormalizedEmailField("Email address", validators=[DataRequired(), Length(max=254), valid_email])
    password = PasswordField("Password", validators=[InputRequired(), Length(min=8, max=128, message="Use between 8 and 128 characters."), strong_password])
    confirm_password = PasswordField("Confirm password", validators=[InputRequired(), EqualTo("password", message="Passwords must match.")])
    submit = SubmitField("Create account")
