# ::krakenw-root

from kraken.common import buildscript

buildscript(requirements=["kraken-build>=0.45.1"])

from kraken.std.aws.lambda_ import python_lambda_zip  # noqa: E402

python_lambda_zip(name="lambda")
