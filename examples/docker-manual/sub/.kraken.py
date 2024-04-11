
from kraken.build import project
from kraken.std.util.render_file_task import RenderFileTask

helloWorld = project.task("helloWorld",RenderFileTask, default=True)
helloWorld.file = project.build_directory / "out.txt"
helloWorld.content.set("Hello, World!")
