# Pins and parts

Which pin of which module carries what, the connectors, the test points, and each
part's name in the code. Written by `circuit/board.py` from the circuit on every
run: change the circuit, not this file.

## Modules

### U1, the ESP32-S3 module

An HW-678 copy of the ESP32-S3-DevKitC-1 (`docs/esp32s3_hw678.md`). The GPIO number in the name is the one the firmware uses.

| Pin | Name | Net | Also on the net |
|---|---|---|---|
| 1 | `3V3` | `ESP_3V3` | supply net, 11 other pins |
| 2 | `3V3` | `ESP_3V3` | supply net, 11 other pins |
| 4 | `GPIO4/ADC1_CH3` | `I2C0_SDA` | J8.3, R12, TP24 |
| 5 | `GPIO5/ADC1_CH4` | `I2C0_SCL` | J8.2, R11, TP25 |
| 6 | `GPIO6/ADC1_CH5` | `SPI3_CS_N` | J10.2, TP20 |
| 7 | `GPIO7/ADC1_CH6` | `SPI3_MOSI` | J10.4, TP22 |
| 8 | `GPIO15/ADC2_CH4/32K_P` | `PANEL_UART_TX` | J12.2, TP29 |
| 9 | `GPIO16/ADC2_CH5/32K_N` | `PANEL_UART_RX` | J12.3, TP28 |
| 10 | `GPIO17/ADC2_CH6` | `I2C1_SDA` | J11.3, R16, TP27 |
| 11 | `GPIO18/ADC2_CH7` | `MIDI1_RX` | R3, TP16, U3.4 |
| 12 | `GPIO8/ADC1_CH7` | `SPI3_SCLK` | J10.3, TP21 |
| 15 | `GPIO9/ADC1_CH8` | `SPI3_MISO` | J10.5, TP23 |
| 16 | `GPIO10/ADC1_CH9` | `SPI2_CS_N` | TP1, U2.9 (28_IOB8B) |
| 17 | `GPIO11/ADC2_CH0` | `SPI2_MOSI` | TP3, U2.11 (26_IOB6B) |
| 18 | `GPIO12/ADC2_CH1` | `SPI2_SCLK` | TP2, U2.10 (25_IOB6A) |
| 19 | `GPIO13/ADC2_CH2` | `SPI2_MISO` | TP4, U2.12 (29_IOB14A) |
| 20 | `GPIO14/ADC2_CH3` | `I2C1_SCL` | J11.2, R15, TP26 |
| 21 | `5V` | `ESP_5V` | supply net, 4 other pins |
| 22 | `GND` | `GND` | supply net, 39 other pins |
| 23 | `GND` | `GND` | supply net, 39 other pins |
| 24 | `GND` | `GND` | supply net, 39 other pins |
| 25 | `GPIO19/USB_D-` | `USB_D-` | J14.A7, J14.B7 |
| 26 | `GPIO20/USB_D+` | `USB_D+` | J14.A6, J14.B6 |
| 41 | `GPIO1/ADC1_CH0` | `MIDI2_RX` | R4, TP30, U4.4 |
| 44 | `GND` | `GND` | supply net, 39 other pins |

Not connected: 3 (`CHIP_PU`), 13 (`GPIO3/ADC1_CH2`), 14 (`GPIO46`), 27 (`GPIO21`), 28 (`GPIO47`), 29 (`GPIO48`), 30 (`GPIO45`), 31 (`GPIO0`), 32 (`GPIO35`), 33 (`GPIO36`), 34 (`GPIO37`), 35 (`GPIO38`), 36 (`GPIO39/MTCK`), 37 (`GPIO40/MTDO`), 38 (`GPIO41/MTDI`), 39 (`GPIO42/MTMS`), 40 (`GPIO2/ADC1_CH1`), 42 (`GPIO44/U0RXD`), 43 (`GPIO43/U0TXD`).

### U2, the Tang Nano 20K

The leading number in the name is the FPGA's pin number, the one the gateware's constraints file uses.

| Pin | Name | Net | Also on the net |
|---|---|---|---|
| 8 | `27_IOB8A` | `SPDIF0` | J5, R7, TP14 |
| 9 | `28_IOB8B` | `SPI2_CS_N` | TP1, U1.16 (GPIO10) |
| 10 | `25_IOB6A` | `SPI2_SCLK` | TP2, U1.18 (GPIO12) |
| 11 | `26_IOB6B` | `SPI2_MOSI` | TP3, U1.17 (GPIO11) |
| 12 | `29_IOB14A` | `SPI2_MISO` | TP4, U1.19 (GPIO13) |
| 20 | `GND` | `GND` | supply net, 40 other pins |
| 25 | `3V3` | `NANO_3V3` | supply net, 1 other pin |
| 26 | `GND` | `GND` | supply net, 40 other pins |
| 28 | `86_IOT4A` | `SPDIF1` | J6, TP15 |
| 30 | `55_IOR36B` | `I2S_WS` | J7.2, TP7, U5.3 (WSEL) |
| 33 | `54_IOR38A` | `I2S_DATA` | J7.4, TP6, U5.4 (DIN) |
| 34 | `56_IOR36A` | `I2S_BCK` | J7.3, TP5, U5.5 (BCK) |
| 39 | `GND` | `GND` | supply net, 40 other pins |
| 40 | `5V` | `NANO_5V` | supply net, 4 other pins |

Not connected: 1 (`73_IOT40A`), 2 (`74_IOT34B`), 3 (`75_IOT34A`), 4 (`85_IOT4B`), 5 (`77_IOT30A`), 6 (`15_IOL46A`), 7 (`16_IOL47B`), 13 (`30_IOB14B`), 14 (`31_IOB29A`), 15 (`17_IOL49A`), 16 (`20_IOL51B`), 17 (`19_IOL51A`), 18 (`18_IOL49B`), 19 (`3V3`), 21 (`52_IOR39A`), 22 (`53_IOR38B`), 23 (`71_IOT44A`), 24 (`72_IOT40B`), 27 (`79_IOT27B`), 29 (`49_IOR49A`), 31 (`48_IOR49B`), 32 (`51_IOR45A`), 35 (`41_IOB43A`), 36 (`42_IOB42B`), 37 (`80_IOT27A`), 38 (`76_IOT30B`).

### U5, the Adafruit PCM510x DAC module

| Pin | Name | Net | Also on the net |
|---|---|---|---|
| 1 | `VIN` | `NANO_5V` | supply net, 4 other pins |
| 2 | `GND` | `GND` | supply net, 42 other pins |
| 3 | `WSEL` | `I2S_WS` | J7.2, TP7, U2.30 (55_IOR36B) |
| 4 | `DIN` | `I2S_DATA` | J7.4, TP6, U2.33 (54_IOR38A) |
| 5 | `BCK` | `I2S_BCK` | J7.3, TP5, U2.34 (56_IOR36A) |
| 6 | `Lout` | `DAC_OUT_L` | J13.2 |
| 7 | `G` | `DAC_OUT_G` | J13.1 |
| 8 | `Rout` | `DAC_OUT_R` | J13.3 |
| 9 | `3V` | `PCM_3V3` | supply net, 3 other pins |
| 10 | `FM` | `DAC_FM` | JP2 |
| 13 | `FIL` | `DAC_FIL` | JP1 |

Not connected: 11 (`MU`), 12 (`MCK`), 14 (`DE`).

## Connectors, headers and jumpers

### J1, `esp32/midi1_input/socket`

| Pin | Name | Net | Also on the net |
|---|---|---|---|
| 4 |  | `MIDI1_SOURCE` | R1 |
| 5 |  | `MIDI1_LED_K` | D1, U3.2 |

Not connected: 1, 2, 3.

### J2, `esp32/midi2_input/socket`

| Pin | Name | Net | Also on the net |
|---|---|---|---|
| 4 |  | `MIDI2_SOURCE` | R2 |
| 5 |  | `MIDI2_LED_K` | D2, U4.2 |

Not connected: 1, 2, 3.

### J3, `tang_nano_20k/spdif0_output/socket`

| Pin | Name | Net | Also on the net |
|---|---|---|---|
| 1 | `In` | `SPDIF0_COAX` | R7, R8 |
| 2 | `Ext` | `GND` | supply net, 42 other pins |

### J5, `tang_nano_20k/spdif0_output/tap`

| Pin | Name | Net | Also on the net |
|---|---|---|---|
| 1 | `Pin_1` | `GND` | supply net, 42 other pins |
| 2 | `Pin_2` | `SPDIF0` | R7, TP14, U2.8 (27_IOB8A) |

### J6, `tang_nano_20k/lab_capture_tap`

| Pin | Name | Net | Also on the net |
|---|---|---|---|
| 1 | `Pin_1` | `GND` | supply net, 42 other pins |
| 2 | `Pin_2` | `SPDIF1` | TP15, U2.28 (86_IOT4A) |

### J7, `tang_nano_20k/i2s_tap`

| Pin | Name | Net | Also on the net |
|---|---|---|---|
| 1 | `Pin_1` | `GND` | supply net, 42 other pins |
| 2 | `Pin_2` | `I2S_WS` | TP7, U2.30 (55_IOR36B), U5.3 (WSEL) |
| 3 | `Pin_3` | `I2S_BCK` | TP5, U2.34 (56_IOR36A), U5.5 (BCK) |
| 4 | `Pin_4` | `I2S_DATA` | TP6, U2.33 (54_IOR38A), U5.4 (DIN) |

### J8, `esp32/i2c0_port/header`

| Pin | Name | Net | Also on the net |
|---|---|---|---|
| 1 | `Pin_1` | `GND` | supply net, 42 other pins |
| 2 | `Pin_2` | `I2C0_SCL` | R11, TP25, U1.5 (GPIO5) |
| 3 | `Pin_3` | `I2C0_SDA` | R12, TP24, U1.4 (GPIO4) |

### J9, `usb/power_socket/socket`

| Pin | Name | Net | Also on the net |
|---|---|---|---|
| A1 | `GND` | `GND` | supply net, 38 other pins |
| A4 | `VBUS` | `EXT_5V` | supply net, 5 other pins |
| A5 | `CC1` | `USB_POWER_CC1` | R13 |
| A9 | `VBUS` | `EXT_5V` | supply net, 5 other pins |
| A12 | `GND` | `GND` | supply net, 38 other pins |
| B1 | `GND` | `GND` | supply net, 38 other pins |
| B4 | `VBUS` | `EXT_5V` | supply net, 5 other pins |
| B5 | `CC2` | `USB_POWER_CC2` | R14 |
| B9 | `VBUS` | `EXT_5V` | supply net, 5 other pins |
| B12 | `GND` | `GND` | supply net, 38 other pins |
| SH | `SHIELD` | `GND` | supply net, 38 other pins |

Not connected: A6 (`D+`), A7 (`D-`), A8 (`SBU1`), B6 (`D+`), B7 (`D-`), B8 (`SBU2`).

### J10, `esp32/spi3_header`

| Pin | Name | Net | Also on the net |
|---|---|---|---|
| 1 | `Pin_1` | `GND` | supply net, 42 other pins |
| 2 | `Pin_2` | `SPI3_CS_N` | TP20, U1.6 (GPIO6) |
| 3 | `Pin_3` | `SPI3_SCLK` | TP21, U1.12 (GPIO8) |
| 4 | `Pin_4` | `SPI3_MOSI` | TP22, U1.7 (GPIO7) |
| 5 | `Pin_5` | `SPI3_MISO` | TP23, U1.15 (GPIO9) |

### J11, `esp32/i2c1_port/header`

| Pin | Name | Net | Also on the net |
|---|---|---|---|
| 1 | `Pin_1` | `GND` | supply net, 42 other pins |
| 2 | `Pin_2` | `I2C1_SCL` | R15, TP26, U1.20 (GPIO14) |
| 3 | `Pin_3` | `I2C1_SDA` | R16, TP27, U1.10 (GPIO17) |

### J12, `esp32/panel_uart_header`

| Pin | Name | Net | Also on the net |
|---|---|---|---|
| 1 | `Pin_1` | `GND` | supply net, 42 other pins |
| 2 | `Pin_2` | `PANEL_UART_TX` | TP29, U1.8 (GPIO15) |
| 3 | `Pin_3` | `PANEL_UART_RX` | TP28, U1.9 (GPIO16) |
| 4 | `Pin_4` | `ESP_5V` | supply net, 4 other pins |

### J13, `tang_nano_20k/analog_out`

| Pin | Name | Net | Also on the net |
|---|---|---|---|
| 1 | `Pin_1` | `DAC_OUT_G` | U5.7 (G) |
| 2 | `Pin_2` | `DAC_OUT_L` | U5.6 (Lout) |
| 3 | `Pin_3` | `DAC_OUT_R` | U5.8 (Rout) |

### J14, `usb/data_socket/socket`

| Pin | Name | Net | Also on the net |
|---|---|---|---|
| A1 | `GND` | `GND` | supply net, 38 other pins |
| A4 | `VBUS` | `USB_DATA_VBUS` |  |
| A5 | `CC1` | `USB_DATA_CC1` | R17 |
| A6 | `D+` | `USB_D+` | U1.26 (GPIO20) |
| A7 | `D-` | `USB_D-` | U1.25 (GPIO19) |
| A9 | `VBUS` | `USB_DATA_VBUS` |  |
| A12 | `GND` | `GND` | supply net, 38 other pins |
| B1 | `GND` | `GND` | supply net, 38 other pins |
| B4 | `VBUS` | `USB_DATA_VBUS` |  |
| B5 | `CC2` | `USB_DATA_CC2` | R18 |
| B6 | `D+` | `USB_D+` | U1.26 (GPIO20) |
| B7 | `D-` | `USB_D-` | U1.25 (GPIO19) |
| B9 | `VBUS` | `USB_DATA_VBUS` |  |
| B12 | `GND` | `GND` | supply net, 38 other pins |
| SH | `SHIELD` | `GND` | supply net, 38 other pins |

Not connected: A8 (`SBU1`), B8 (`SBU2`).

### JP1, `tang_nano_20k/filter_jumper`

| Pin | Name | Net | Also on the net |
|---|---|---|---|
| 1 | `A` | `PCM_3V3` | supply net, 3 other pins |
| 2 | `B` | `DAC_FIL` | U5.13 (FIL) |

### JP2, `tang_nano_20k/format_jumper`

| Pin | Name | Net | Also on the net |
|---|---|---|---|
| 1 | `A` | `PCM_3V3` | supply net, 3 other pins |
| 2 | `B` | `DAC_FM` | U5.10 (FM) |

## Test points

| Test point | Net |
|---|---|
| TP1 | `SPI2_CS_N` |
| TP2 | `SPI2_SCLK` |
| TP3 | `SPI2_MOSI` |
| TP4 | `SPI2_MISO` |
| TP5 | `I2S_BCK` |
| TP6 | `I2S_DATA` |
| TP7 | `I2S_WS` |
| TP8 | `EXT_5V` |
| TP9 | `ESP_5V` |
| TP10 | `ESP_3V3` |
| TP11 | `NANO_5V` |
| TP12 | `NANO_3V3` |
| TP13 | `PCM_3V3` |
| TP14 | `SPDIF0` |
| TP15 | `SPDIF1` |
| TP16 | `MIDI1_RX` |
| TP18 | `GND` |
| TP19 | `GND` |
| TP20 | `SPI3_CS_N` |
| TP21 | `SPI3_SCLK` |
| TP22 | `SPI3_MOSI` |
| TP23 | `SPI3_MISO` |
| TP24 | `I2C0_SDA` |
| TP25 | `I2C0_SCL` |
| TP26 | `I2C1_SCL` |
| TP27 | `I2C1_SDA` |
| TP28 | `PANEL_UART_RX` |
| TP29 | `PANEL_UART_TX` |
| TP30 | `MIDI2_RX` |

## Parts by designator

The name in the code is the sheet, the block if the part is in one, and the
part's own name.

| Designator | Name in the code | Value |
|---|---|---|
| C1 | `usb/power_socket/esp_5v_supply/input_capacitor` | 1u |
| C2 | `usb/power_socket/nano_5v_supply/input_capacitor` | 1u |
| C3 | `esp32/midi1_input/bypass` | 100n |
| C4 | `esp32/midi2_input/bypass` | 100n |
| D1 | `esp32/midi1_input/clamp` | 1N4148W |
| D2 | `esp32/midi2_input/clamp` | 1N4148W |
| H1 | `mounting_holes/h1` | MountingHole |
| H2 | `mounting_holes/h2` | MountingHole |
| H3 | `mounting_holes/h3` | MountingHole |
| H4 | `mounting_holes/h4` | MountingHole |
| J1 | `esp32/midi1_input/socket` | Lumberg_0105_05 |
| J2 | `esp32/midi2_input/socket` | Lumberg_0105_05 |
| J3 | `tang_nano_20k/spdif0_output/socket` | Conn_Coaxial |
| J5 | `tang_nano_20k/spdif0_output/tap` | Conn_01x02_Pin |
| J6 | `tang_nano_20k/lab_capture_tap` | Conn_01x02_Pin |
| J7 | `tang_nano_20k/i2s_tap` | Conn_01x04_Pin |
| J8 | `esp32/i2c0_port/header` | Conn_01x03_Pin |
| J9 | `usb/power_socket/socket` | USB_C_Receptacle_USB2.0_16P |
| J10 | `esp32/spi3_header` | Conn_01x05_Pin |
| J11 | `esp32/i2c1_port/header` | Conn_01x03_Pin |
| J12 | `esp32/panel_uart_header` | Conn_01x04_Pin |
| J13 | `tang_nano_20k/analog_out` | Conn_01x03_Pin |
| J14 | `usb/data_socket/socket` | USB_C_Receptacle_USB2.0_16P |
| JP1 | `tang_nano_20k/filter_jumper` | Jumper_2_Open |
| JP2 | `tang_nano_20k/format_jumper` | Jumper_2_Open |
| R1 | `esp32/midi1_input/series` | 220 |
| R2 | `esp32/midi2_input/series` | 220 |
| R3 | `esp32/midi1_input/pullup` | 470 |
| R4 | `esp32/midi2_input/pullup` | 470 |
| R7 | `tang_nano_20k/spdif0_output/series` | 220 |
| R8 | `tang_nano_20k/spdif0_output/shunt` | 120 |
| R11 | `esp32/i2c0_port/scl_pullup` | 4.7k |
| R12 | `esp32/i2c0_port/sda_pullup` | 4.7k |
| R13 | `usb/power_socket/cc1_pulldown` | 5.1k |
| R14 | `usb/power_socket/cc2_pulldown` | 5.1k |
| R15 | `esp32/i2c1_port/scl_pullup` | 4.7k |
| R16 | `esp32/i2c1_port/sda_pullup` | 4.7k |
| R17 | `usb/data_socket/cc1_pulldown` | 5.1k |
| R18 | `usb/data_socket/cc2_pulldown` | 5.1k |
| U1 | `esp32/esp` | ESP32-S3-DevKitC |
| U2 | `tang_nano_20k/fpga` | Tang_Nano_20K |
| U3 | `esp32/midi1_input/opto` | H11L1 |
| U4 | `esp32/midi2_input/opto` | H11L1 |
| U5 | `tang_nano_20k/dac` | Adafruit_PCM510x |
| U6 | `usb/power_socket/esp_5v_supply/diode` | LM66100DCK |
| U7 | `usb/power_socket/nano_5v_supply/diode` | LM66100DCK |
