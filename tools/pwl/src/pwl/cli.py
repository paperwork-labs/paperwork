import typer

from pwl.commands.doctor import doctor
from pwl.commands.list_apps import list_apps
from pwl.commands.new_app import new_app
from pwl.commands.onboard import onboard
from pwl.commands.registry_build import registry_build
from pwl.commands.version import version

app = typer.Typer(
    help="Paperwork Labs CLI — scaffold new apps and audit monorepo health.",
    no_args_is_help=True,
)

app.command("version")(version)
app.command("list-apps")(list_apps)
app.command("doctor")(doctor)
app.command("new-app")(new_app)
app.command("onboard")(onboard)
app.command("registry-build")(registry_build)
