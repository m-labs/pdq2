f1/trigger: trigger
f2: cs_n
f3: sclk
f4: mosi
f5 out: miso/aux

usb: escaper (-> eop)
spi: slave

8 bit stx (only parallel protocol)
8 bit header (msb-to-lsb):
  1 read/write_b
  4 board addr 0xf=all
  1 mem/reg
  2 addr

2 bit addr reg:
  8 config:
    1 reset
    1 dcm
    1 enable
    1 soft_trigger
    1 f5_is_aux
    3 f5_mask
  8 checksum 
  8 current frame

2 bit addr mem sel:
  memory0
  memory1
  memory2

8 bit reg data read/write

16 bit mem addr (write with auto-increasing address):
n x 16 bit mem data read/write

8 bit etx (only parallel protocol)
