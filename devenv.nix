{ pkgs, lib, ... }:

{
  scripts.install_firmware = {
    exec = ''
      ${lib.getExe pkgs.unzip} ~/Downloads/firmware.zip -d /tmp/adv360pro-firmware
      sudo mount --mkdir /dev/disk/by-id/usb-Adafruit_nRF_UF2_92C5A21B39C4917B-0:0 /mnt/left
      sudo mount --mkdir /dev/disk/by-id/usb-Adafruit_nRF_UF2_47AB871917154762-0:0 /mnt/right
      sudo mv /tmp/adv360pro-firmware/adv360pro_left-zmk.uf2 /mnt/left
      sudo mv /tmp/adv360pro-firmware/adv360pro_right-zmk.uf2 /mnt/right
      while true
        read -l -P 'Do you want to continue? [y/N] ' confirm
        switch $confirm
          case Y y
            sudo umount /mnt/left
            sudo umount /mnt/right
            return 0
          case "" N n
            return 1
        end
      end
      printf "Firmware flashed\n"
    '';
    package = pkgs.fish;
  };
  scripts.umount_keyboard = {
    exec = ''
      sudo umount /mnt/left
      sudo umount /mnt/right
    '';
  };
}
