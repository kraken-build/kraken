{
  description = "Development environment with Python 3.10, 3.11, 3.12 and required CLI tools";

  inputs = {
    nixpkgs.url = "nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem
      (system:
        let
          pkgs = import nixpkgs { inherit system; };
        in
        {
          devShells.default = pkgs.mkShell {
            buildInputs = [
              pkgs.python310
              pkgs.python311
              pkgs.python312
              pkgs.python310Packages.pip
            ];
          };
        }
      );
}
