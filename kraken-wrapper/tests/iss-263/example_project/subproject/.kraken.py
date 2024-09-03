from dependency import answer_to_the_universe
from kraken.build import project

path = project.directory / "answer.txt"
print("Writing file", path)
path.write_text(str(answer_to_the_universe()))
