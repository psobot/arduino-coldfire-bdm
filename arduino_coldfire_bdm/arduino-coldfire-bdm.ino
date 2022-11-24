#pragma GCC optimize("-O3")
#pragma GCC push_options

// Coldfire BDM Serial Bridge
// by Peter Sobot (@psobot), November 8, 2022

// Two inputs to the Coldfire:
int DSCLK = 2;
int DSI = 3;

// Trigger a breakpoint by pulling this low:
int BKPT = 4; // Low = 1, High = 0

// One output from the Coldfire, which is visible a couple CPU clock cycles
// after the fall of DSCLK. In practice, this means we only need to wait ~30
// nanoseconds between fall of DSCLK and seeing the correct value on DSO.
int DSO = 5;
int RESET = 7;

// Serial data is sent in 17-bit packets:
//  Receive (by the Coldfire): [status] [16 bits of data]
//  Send (to the Coldfire): [0] [16 bits of data]

struct Packet {
  uint8_t status;
  uint16_t data;
};

// The protocol here is technically full-duplex; commands can be sent and
// received simultaneously.
bool sendAndReceiveBit(uint8_t bitToSend) {
  digitalWrite(DSI, bitToSend);
  digitalWrite(DSCLK, HIGH);
  digitalWrite(DSCLK, LOW);
  return digitalRead(DSO);
}

bool receiveBit() { return sendAndReceiveBit(0); }

void sendBit(uint8_t bit) { sendAndReceiveBit(bit); }

Packet receivePacket() { return sendAndReceivePacket(0); }

Packet sendAndReceivePacket(uint16_t dataToSend) {
  Packet packet;

  packet.status = 0;
  packet.data = 0;

  packet.status = sendAndReceiveBit(0);
  for (int i = 15; i >= 0; i--) {
    packet.data |= sendAndReceiveBit((dataToSend >> i) & 1) << i;
  }

  return packet;
}

void sendPacket(uint16_t data) {
  sendBit(0);

  for (int i = 15; i >= 0; i--) {
    char singleBit = (data >> i) & 1;
    sendBit(singleBit);
  }
}

void enterDebugMode(bool reset) {
  digitalWrite(BKPT, LOW);
  pinMode(BKPT, OUTPUT);
  delay(50);

  if (reset) {
    digitalWrite(RESET, LOW);
    pinMode(RESET, OUTPUT);
    delay(50);

    pinMode(RESET, INPUT);
    delay(50);
  }

  pinMode(BKPT, INPUT);
  delay(50);
}

void setup() {
  Serial.begin(1000000);
  Serial.println("Motorola Coldfire Debug Interface by Peter Sobot");

  pinMode(DSCLK, OUTPUT);
  pinMode(DSI, OUTPUT);
  pinMode(DSO, INPUT);

  Serial.println("Ready.");
}

uint16_t getNextTwoBytesFromUSB() {
  while (!Serial.available()) {
  }
  uint16_t data = ((uint16_t)Serial.read()) << 8;
  while (!Serial.available()) {
  }
  data |= Serial.read();
  return data;
}

void loop() {
  if (Serial.available() > 0) {
    int command = Serial.read();

    switch (command) {
    case 'P': // for Ping
      Serial.println("PONG");
      break;
    case 'B': // for Breakpoint
      enterDebugMode(false);
      break;
    case 'R': // for Reset
      enterDebugMode(true);
      break;
    case 'S': { // for Send-and-Receive
      uint16_t data = getNextTwoBytesFromUSB();
      Packet packet = sendAndReceivePacket(data);
      Serial.print(packet.status ? "Y" : "N");
      Serial.write((char *)&packet.data, sizeof(packet.data));
      break;
    }
    case 's': { // for Send
      sendPacket(getNextTwoBytesFromUSB());
      break;
    }
    case 'r': { // for Receive
      Packet packet = receivePacket();
      Serial.print(packet.status ? "Y" : "N");
      Serial.write((char *)&packet.data, sizeof(packet.data));
      break;
    }
    }
  }
}
