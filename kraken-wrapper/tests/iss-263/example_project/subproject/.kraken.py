from pathlib import Path
from dependency import answer_to_the_universe

Path("answer.txt").write_text(str(answer_to_the_universe()))
