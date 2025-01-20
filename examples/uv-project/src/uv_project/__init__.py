from time import sleep

from tqdm import tqdm


def hello() -> None:
    for _ in tqdm(range(10)):
        print("Hello from uv-project!")
        sleep(1)
