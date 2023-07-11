{
  description = "Flake to create kraken wrapper application";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    poetry2nix = {
      url = "github:nix-community/poetry2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, poetry2nix, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        overlays = [ poetry2nix.overlay ];
        pkgs = import nixpkgs {
          inherit system overlays;
        };
      in
      rec {
        packages = flake-utils.lib.flattenTree rec {
          krakenw = (pkgs.poetry2nix.mkPoetryApplication {
            projectDir = ./kraken-wrapper;
          });
          default = krakenw;
        };
      }
    );
}
