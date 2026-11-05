#include <LiquidCrystal.h>
#include <Servo.h>

const uint8_t PIN_BIT_ONE = 13;
const uint8_t PIN_BIT_ZERO = 12;
const uint8_t PIN_SERVO = 9;
const unsigned long SERIAL_BAUD = 115200;
const unsigned int BIT_PULSE_MS = 20;

LiquidCrystal lcd(7, 6, 5, 4, 3, 2);
Servo valueServo;

char inputLine[34];
uint8_t inputLength = 0;
bool inputOverflow = false;

uint8_t reverseByte(uint8_t value) {
  uint8_t reversed = 0;
  for (uint8_t bit = 0; bit < 8; bit++) {
    reversed = (reversed << 1) | (value & 1);
    value >>= 1;
  }
  return reversed;
}

bool hasOddParity(uint32_t word) {
  uint8_t ones = 0;
  for (uint8_t bit = 0; bit < 32; bit++) {
    ones += word & 1;
    word >>= 1;
  }
  return (ones & 1) == 1;
}

bool parseWord(const char *text, uint32_t &word) {
  if (*text == '\0' || *text == '-') return false;

  uint8_t base = 10;
  if (text[0] == '0' && (text[1] == 'x' || text[1] == 'X')) {
    base = 16;
    text += 2;
  } else if (text[0] == '0' && (text[1] == 'b' || text[1] == 'B')) {
    base = 2;
    text += 2;
  } else {
    bool binaryText = true;
    uint8_t length = 0;
    for (const char *cursor = text; *cursor; cursor++) {
      if (*cursor != '0' && *cursor != '1') binaryText = false;
      length++;
    }
    if (binaryText && length == 32) base = 2;
  }

  if (*text == '\0') return false;
  uint32_t parsed = 0;
  for (; *text; text++) {
    uint8_t digit;
    if (*text >= '0' && *text <= '9') digit = *text - '0';
    else if (*text >= 'a' && *text <= 'f') digit = *text - 'a' + 10;
    else if (*text >= 'A' && *text <= 'F') digit = *text - 'A' + 10;
    else return false;
    if (digit >= base || parsed > (0xFFFFFFFFUL - digit) / base) return false;
    parsed = parsed * base + digit;
  }
  word = parsed;
  return true;
}

void showError(const char *message) {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("TRAMA INVALIDA");
  lcd.setCursor(0, 1);
  lcd.print(message);
  Serial.print("ERROR: ");
  Serial.println(message);
}

void sendOneHotBits(uint32_t word) {
  for (int8_t bit = 31; bit >= 0; bit--) {
    digitalWrite(PIN_BIT_ONE, LOW);
    digitalWrite(PIN_BIT_ZERO, LOW);
    delay(2);

    if ((word >> bit) & 1UL) digitalWrite(PIN_BIT_ONE, HIGH);
    else digitalWrite(PIN_BIT_ZERO, HIGH);
    delay(BIT_PULSE_MS);

    digitalWrite(PIN_BIT_ONE, LOW);
    digitalWrite(PIN_BIT_ZERO, LOW);
    delay(2);
  }
}

void processWord(uint32_t word) {
  if (!hasOddParity(word)) {
    digitalWrite(PIN_BIT_ONE, LOW);
    digitalWrite(PIN_BIT_ZERO, LOW);
    showError("PARIDAD IMPAR");
    return;
  }

  uint8_t label = reverseByte(word & 0xFF);
  uint8_t sdi = (word >> 8) & 0x03;
  uint8_t ssm = (word >> 29) & 0x03;
  uint32_t data = (word >> 10) & 0x7FFFFUL;

  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("LBL:");
  if (label < 64) lcd.print('0');
  if (label < 8) lcd.print('0');
  lcd.print(label, OCT);
  lcd.print(" D:");
  lcd.print(data);
  lcd.setCursor(0, 1);
  lcd.print("PAR:OK S:");
  lcd.print(sdi);
  lcd.print(" M:");
  lcd.print(ssm);

  uint8_t servoAngle = (uint32_t)data * 180UL / 0x7FFFFUL;
  valueServo.write(servoAngle);
  sendOneHotBits(word);

  Serial.print("OK LABEL_OCT=");
  if (label < 64) Serial.print('0');
  if (label < 8) Serial.print('0');
  Serial.print(label, OCT);
  Serial.print(" SDI=");
  Serial.print(sdi);
  Serial.print(" DATA=");
  Serial.print(data);
  Serial.print(" SSM=");
  Serial.print(ssm);
  Serial.print(" SERVO_DEG=");
  Serial.println(servoAngle);
}

void handleSerialLine() {
  inputLine[inputLength] = '\0';
  if (inputOverflow) {
    showError("LINEA MUY LARGA");
  } else {
    uint32_t word;
    if (!parseWord(inputLine, word)) showError("FORMATO SERIAL");
    else processWord(word);
  }
  inputLength = 0;
  inputOverflow = false;
}

void setup() {
  pinMode(PIN_BIT_ONE, OUTPUT);
  pinMode(PIN_BIT_ZERO, OUTPUT);
  digitalWrite(PIN_BIT_ONE, LOW);
  digitalWrite(PIN_BIT_ZERO, LOW);

  lcd.begin(16, 2);
  valueServo.attach(PIN_SERVO);
  valueServo.write(0);
  Serial.begin(SERIAL_BAUD);

  lcd.setCursor(0, 0);
  lcd.print("ARINC 429 RX");
  lcd.setCursor(0, 1);
  lcd.print("115200 bps");
  Serial.println("Listo. Envie una palabra ARINC por linea.");
}

void loop() {
  while (Serial.available() > 0) {
    char incoming = Serial.read();
    if (incoming == '\r') continue;
    if (incoming == '\n') {
      if (inputLength || inputOverflow) handleSerialLine();
      continue;
    }
    if (incoming == ' ' || incoming == '\t') continue;

    if (inputLength < sizeof(inputLine) - 1) inputLine[inputLength++] = incoming;
    else inputOverflow = true;
  }
}
