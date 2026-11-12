{
  description = "ZMK firmware for the Kinesis Advantage 360 Pro";

  # Local alternative to the GitHub Actions build (build.yaml). Usage:
  #
  #   nix build          # ./result/zmk_left.uf2 and ./result/zmk_right.uf2
  #   nix run .#flash    # flash both halves, right first, then left
  #   nix run .#flash -- left
  #
  # When config/west.yml changes, the build fails with a hash mismatch for
  # the west deps. Copy the "got:" hash into zephyrDepsHash below.
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";

    zmk-nix = {
      url = "github:lilyinstarlight/zmk-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = {
    nixpkgs,
    zmk-nix,
    ...
  }: let
    forAllSystems = nixpkgs.lib.genAttrs (nixpkgs.lib.attrNames zmk-nix.packages);
  in {
    packages = forAllSystems (system: rec {
      default = firmware;

      firmware = zmk-nix.legacyPackages.${system}.buildSplitKeyboard {
        name = "adv360pro";

        src = nixpkgs.lib.sourceFilesBySuffices ./. [".conf" ".dtsi" ".h" ".keymap" ".overlay" ".yml"];

        # Matches build.yaml: Studio is only built into the central (left) half.
        board = "adv360pro_%PART%//zmk";
        enableZmkStudio = true;

        # `nix run .#flash` flashes parts in this order. Right goes first so
        # the halves are still connected and the right half's &bootloader key
        # works. Flash left first and a split-protocol change can strand the
        # right half until you use its pinhole reset button.
        parts = ["right" "left"];
        centralPart = "left";

        zephyrDepsHash = "sha256-j/+xWtd/uqwdgna25I8uQBFwotMoTNcLdPOtEmUASHU=";

        meta = {
          description = "ZMK firmware for the Kinesis Advantage 360 Pro";
          license = nixpkgs.lib.licenses.mit;
          platforms = nixpkgs.lib.platforms.all;
        };
      };

      flash = zmk-nix.packages.${system}.flash.override {inherit firmware;};
    });
  };
}
