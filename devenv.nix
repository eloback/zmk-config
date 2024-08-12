{ pkgs, lib, ... }:
let
  firmware_path = "~/Downloads/firmware.zip";
  firmware_out_path = "/tmp/adv360pro-firmware";
  left_mount_path = "/mnt/left";
  right_mount_path = "/mnt/right";
  left_device_path = "/dev/disk/by-id/usb-Adafruit_nRF_UF2_92C5A21B39C4917B-0:0";
  right_device_path = "/dev/disk/by-id/usb-Adafruit_nRF_UF2_47AB871917154762-0:0";
  unmountKeyboardBySide = side: ''
    sudo umount ${if side == "left" then left_mount_path else right_mount_path}
  '';
  generateInstallScriptBySide = side: {
    exec = ''
      sudo mount --mkdir ${if side == "left" then left_device_path else right_device_path} ${if side == "left" then left_mount_path else right_mount_path}
      sudo mv /tmp/adv360pro-firmware/adv360pro_${side}-zmk.uf2 ${if side == "left" then left_mount_path else right_mount_path}
      read -l -P 'Do you want to continue? [y/N] ' confirm
      switch $confirm
        case Y y
          ${unmountKeyboardBySide side}
          printf "Firmware flashed\n"
          return 0
        case '''' N n
          return 1
      end
    '';
    package = pkgs.fish;
  };
in
{
  scripts = {
    generate_firm = {
      exec = ''
        ${lib.getExe pkgs.unzip} ${firmware_path} -d ${firmware_out_path}
      '';
    };
    install_left = generateInstallScriptBySide "left";
    install_right = generateInstallScriptBySide "right";
    install_all = {
      exec = ''
        generate_firm
        install_left && install_right
        rm -rf ${firmware_out_path}
      '';
      package = pkgs.fish;
    };
  };
}
