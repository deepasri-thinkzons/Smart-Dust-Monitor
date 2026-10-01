#define BLYNK_TEMPLATE_ID "TMPL3VkDTFqiS"
#define BLYNK_TEMPLATE_NAME "Dust Monitor Project"
#define BLYNK_AUTH_TOKEN "YOUR_BLYNK_AUTH_TOKEN"

#include <WiFi.h>
#include <HTTPClient.h>
#include <BlynkSimpleEsp32.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <DHT.h>
#include <math.h>

char ssid[] = "YOUR_WIFI_SSID";
char pass[] = "YOUR_WIFI_PASSWORD";
const char* PC_SERVER_URL = "http://YOUR_PC_IP:5000/api/sample";


// ============================================================
// PINS
// ============================================================

#define MQ135_PIN 34
#define DHT_PIN 4
#define DHT_TYPE DHT11
#define BUZZER_PIN 25

#define LCD_SDA 21
#define LCD_SCL 22


// ============================================================
// MQ-135 CONSTANTS
// ============================================================

const float ADC_MAX = 4095.0;
const float ADC_VOLTAGE = 3.3;

const float SENSOR_VOLTAGE = 5.0;

// Your existing value
const float RL = 1000.0;

// Your existing clean-air ADC reference
const float CLEAN_ADC = 2200.0;


// ============================================================
// CALIBRATION
// ============================================================

float R0 = 0;

float A = 0;
float B = 0;

bool AB_Calculated = false;


// ============================================================
// OBJECTS
// ============================================================

DHT dht(DHT_PIN, DHT_TYPE);

LiquidCrystal_I2C lcd(
  0x27,
  16,
  2
);

BlynkTimer timer;


// ============================================================
// SENSOR VARIABLES
// ============================================================

float currentADC = 0;

float currentVoltage = 0;

float currentRs = 0;

float currentRatio = 0;

float currentPPM = 0;

float currentTemperature = 0;

float currentHumidity = 0;

String statusText = "UNKNOWN";


// ============================================================
// TIMERS
// ============================================================

unsigned long lastBuzzer = 0;

unsigned long lastWiFiCheck = 0;

unsigned long lastPCPost = 0;

unsigned long lastSerialStatus = 0;


// ============================================================
// CONNECTION SETTINGS
// ============================================================

const unsigned long SENSOR_INTERVAL = 1000;

const unsigned long PC_POST_INTERVAL = 1000;

const unsigned long WIFI_CHECK_INTERVAL = 5000;


// ============================================================
// CALCULATE Rs
// ============================================================

float calculateRs(float adc)
{
  float voltage =
    (adc / ADC_MAX) * ADC_VOLTAGE;

  if (voltage <= 0.01)
  {
    return 0;
  }

  float rs =
    RL *
    (SENSOR_VOLTAGE - voltage) /
    voltage;

  if (rs < 0)
  {
    rs = 0;
  }

  return rs;
}


// ============================================================
// AVERAGE MQ-135 ADC
// ============================================================

float readAverageADC()
{
  long total = 0;

  const int samples = 10;

  for (int i = 0; i < samples; i++)
  {
    total += analogRead(MQ135_PIN);

    delay(5);
  }

  return
    (float)total /
    (float)samples;
}


// ============================================================
// AIR STATUS
// ============================================================

String getStatus(float ppm)
{
  if (ppm <= 400)
  {
    return "EXCELLENT";
  }

  if (ppm <= 1000)
  {
    return "GOOD";
  }

  if (ppm <= 2000)
  {
    return "MODERATE";
  }

  if (ppm <= 5000)
  {
    return "POOR";
  }

  return "CRITICAL";
}


// ============================================================
// BUZZER
// ============================================================

void alertBuzzer()
{
  unsigned long now =
    millis();


  if (
    statusText == "POOR" &&
    now - lastBuzzer >= 2000
  )
  {
    tone(
      BUZZER_PIN,
      2200,
      150
    );

    lastBuzzer = now;
  }


  else if (
    statusText == "CRITICAL" &&
    now - lastBuzzer >= 700
  )
  {
    tone(
      BUZZER_PIN,
      2500,
      250
    );

    lastBuzzer = now;
  }
}


// ============================================================
// WIFI STATUS
// ============================================================

void checkWiFi()
{
  if (
    millis() - lastWiFiCheck <
    WIFI_CHECK_INTERVAL
  )
  {
    return;
  }

  lastWiFiCheck =
    millis();


  if (WiFi.status() == WL_CONNECTED)
  {
    return;
  }


  Serial.println();
  Serial.println(
    "[WiFi] Connection lost."
  );

  Serial.println(
    "[WiFi] Reconnecting..."
  );


  WiFi.disconnect();

  WiFi.begin(
    ssid,
    pass
  );
}


// ============================================================
// PRINT WIFI INFORMATION
// ============================================================

void printWiFiInfo()
{
  Serial.println();
  Serial.println(
    "======================================"
  );

  Serial.println(
    "ESP32 NETWORK INFORMATION"
  );

  Serial.println(
    "======================================"
  );

  Serial.print(
    "SSID: "
  );

  Serial.println(
    WiFi.SSID()
  );

  Serial.print(
    "ESP32 IP: "
  );

  Serial.println(
    WiFi.localIP()
  );

  Serial.print(
    "Gateway: "
  );

  Serial.println(
    WiFi.gatewayIP()
  );

  Serial.print(
    "RSSI: "
  );

  Serial.print(
    WiFi.RSSI()
  );

  Serial.println(
    " dBm"
  );

  Serial.print(
    "PC Flask URL: "
  );

  Serial.println(
    PC_SERVER_URL
  );

  Serial.println(
    "======================================"
  );

  Serial.println();
}


// ============================================================
// SEND DATA TO FLASK
// ============================================================

void postToPC()
{
  if (
    WiFi.status() != WL_CONNECTED
  )
  {
    Serial.println(
      "[PC] WiFi not connected."
    );

    return;
  }


  HTTPClient http;


  // ----------------------------------------------------------
  // Set short connection timeout
  // ----------------------------------------------------------

  http.setConnectTimeout(
    2000
  );

  http.setTimeout(
    3000
  );


  Serial.print(
    "[PC] POST -> "
  );

  Serial.println(
    PC_SERVER_URL
  );


  // ----------------------------------------------------------
  // Begin HTTP
  // ----------------------------------------------------------

  if (
    !http.begin(
      PC_SERVER_URL
    )
  )
  {
    Serial.println(
      "[PC] HTTP begin FAILED"
    );

    return;
  }


  // ----------------------------------------------------------
  // Header
  // ----------------------------------------------------------

  http.addHeader(
    "Content-Type",
    "application/json"
  );


  // ----------------------------------------------------------
  // JSON
  // ----------------------------------------------------------

  String body = "{";


  body +=
    "\"source\":\"ESP32\",";


  body +=
    "\"device_ms\":" +
    String(millis()) +
    ",";


  body +=
    "\"adc\":" +
    String(
      currentADC,
      1
    ) +
    ",";


  body +=
    "\"voltage\":" +
    String(
      currentVoltage,
      4
    ) +
    ",";


  body +=
    "\"rs\":" +
    String(
      currentRs,
      2
    ) +
    ",";


  body +=
    "\"r0\":" +
    String(
      R0,
      2
    ) +
    ",";


  body +=
    "\"ratio\":" +
    String(
      currentRatio,
      6
    ) +
    ",";


  body +=
    "\"ppm\":" +
    String(
      currentPPM,
      2
    ) +
    ",";


  body +=
    "\"temperature\":" +
    String(
      currentTemperature,
      2
    ) +
    ",";


  body +=
    "\"humidity\":" +
    String(
      currentHumidity,
      2
    ) +
    ",";


  body +=
    "\"status\":\"" +
    statusText +
    "\"";


  body += "}";


  // ----------------------------------------------------------
  // Print JSON
  // ----------------------------------------------------------

  Serial.println(
    "[PC] JSON:"
  );

  Serial.println(
    body
  );


  // ----------------------------------------------------------
  // POST
  // ----------------------------------------------------------

  int httpCode =
    http.POST(
      body
    );


  // ----------------------------------------------------------
  // Check result
  // ----------------------------------------------------------

  if (
    httpCode > 0
  )
  {
    Serial.print(
      "[PC] HTTP CODE: "
    );

    Serial.println(
      httpCode
    );


    String response =
      http.getString();


    Serial.print(
      "[PC] RESPONSE: "
    );

    Serial.println(
      response
    );


    if (
      httpCode == 200
    )
    {
      Serial.println(
        "[PC] DATA RECEIVED BY FLASK"
      );
    }
    else
    {
      Serial.println(
        "[PC] Flask returned an error."
      );
    }
  }

  else
  {
    Serial.print(
      "[PC] POST FAILED: "
    );

    Serial.println(
      http.errorToString(
        httpCode
      )
    );
  }


  http.end();

  Serial.println();
}


// ============================================================
// READ SENSOR
// ============================================================

void readSensor()
{
  // ----------------------------------------------------------
  // MQ-135
  // ----------------------------------------------------------

  currentADC =
    readAverageADC();


  currentVoltage =
    (currentADC / ADC_MAX) *
    ADC_VOLTAGE;


  currentRs =
    calculateRs(
      currentADC
    );


  // ----------------------------------------------------------
  // R0
  // ----------------------------------------------------------

  if (R0 > 0)
  {
    currentRatio =
      currentRs / R0;
  }
  else
  {
    currentRatio = 0;
  }


  // ----------------------------------------------------------
  // DHT11
  // ----------------------------------------------------------

  float t =
    dht.readTemperature();

  float h =
    dht.readHumidity();


  if (!isnan(t))
  {
    currentTemperature =
      t;
  }


  if (!isnan(h))
  {
    currentHumidity =
      h;
  }


  // ----------------------------------------------------------
  // PPM
  // ----------------------------------------------------------

  if (
    AB_Calculated &&
    currentRatio > 0
  )
  {
    currentPPM =
      A *
      pow(
        currentRatio,
        B
      );
  }

  else
  {
    if (
      currentRs > 0 &&
      R0 > 0
    )
    {
      currentPPM =
        400.0 *
        pow(
          R0 / currentRs,
          2.0
        );
    }
    else
    {
      currentPPM = 0;
    }
  }


  // ----------------------------------------------------------
  // Prevent invalid value
  // ----------------------------------------------------------

  if (
    isnan(currentPPM) ||
    isinf(currentPPM) ||
    currentPPM < 0
  )
  {
    currentPPM = 0;
  }


  // ----------------------------------------------------------
  // Status
  // ----------------------------------------------------------

  statusText =
    getStatus(
      currentPPM
    );


  // ----------------------------------------------------------
  // Buzzer
  // ----------------------------------------------------------

  alertBuzzer();


  // ----------------------------------------------------------
  // BLYNK
  // ----------------------------------------------------------

  if (
    Blynk.connected()
  )
  {
    Blynk.virtualWrite(
      V0,
      currentADC
    );

    Blynk.virtualWrite(
      V1,
      currentRatio
    );

    Blynk.virtualWrite(
      V2,
      currentPPM
    );

    Blynk.virtualWrite(
      V3,
      currentTemperature
    );

    Blynk.virtualWrite(
      V4,
      currentHumidity
    );

    Blynk.virtualWrite(
      V12,
      statusText
    );
  }


  // ----------------------------------------------------------
  // LCD
  // ----------------------------------------------------------

  lcd.clear();


  lcd.setCursor(
    0,
    0
  );

  lcd.print(
    "PPM:"
  );

  lcd.print(
    currentPPM,
    0
  );


  lcd.setCursor(
    0,
    1
  );

  lcd.print(
    statusText.substring(
      0,
      10
    )
  );


  // ----------------------------------------------------------
  // Send to PC
  // ----------------------------------------------------------

  if (
    millis() - lastPCPost >=
    PC_POST_INTERVAL
  )
  {
    lastPCPost =
      millis();

    postToPC();
  }


  // ----------------------------------------------------------
  // Serial sensor information
  // ----------------------------------------------------------

  Serial.printf(
    "ADC %.0f | "
    "V %.3f | "
    "Rs %.1f | "
    "R0 %.1f | "
    "Ratio %.4f | "
    "PPM %.1f | "
    "T %.1f | "
    "H %.1f | "
    "%s\n",

    currentADC,

    currentVoltage,

    currentRs,

    R0,

    currentRatio,

    currentPPM,

    currentTemperature,

    currentHumidity,

    statusText.c_str()
  );
}


// ============================================================
// SETUP
// ============================================================

void setup()
{
  Serial.begin(
    115200
  );


  delay(1000);


  Serial.println();
  Serial.println(
    "======================================"
  );

  Serial.println(
    "MQ-135 ESP32 LOCAL AI SENSOR"
  );

  Serial.println(
    "======================================"
  );


  // ----------------------------------------------------------
  // GPIO
  // ----------------------------------------------------------

  pinMode(
    BUZZER_PIN,
    OUTPUT
  );


  // ----------------------------------------------------------
  // ADC
  // ----------------------------------------------------------

  analogReadResolution(
    12
  );


  // ----------------------------------------------------------
  // DHT
  // ----------------------------------------------------------

  dht.begin();


  // ----------------------------------------------------------
  // I2C
  // ----------------------------------------------------------

  Wire.begin(
    LCD_SDA,
    LCD_SCL
  );


  // ----------------------------------------------------------
  // LCD
  // ----------------------------------------------------------

  lcd.init();

  lcd.backlight();


  lcd.clear();

  lcd.setCursor(
    0,
    0
  );

  lcd.print(
    "MQ135 + DHT11"
  );


  lcd.setCursor(
    0,
    1
  );

  lcd.print(
    "Connecting..."
  );


  // ----------------------------------------------------------
  // Calculate initial R0
  // ----------------------------------------------------------

  R0 =
    calculateRs(
      CLEAN_ADC
    );


  Serial.print(
    "Initial R0 = "
  );

  Serial.println(
    R0
  );


  // ----------------------------------------------------------
  // WiFi
  // ----------------------------------------------------------

  WiFi.mode(
    WIFI_STA
  );


  WiFi.setAutoReconnect(
    true
  );


  WiFi.persistent(
    false
  );


  Serial.println();
  Serial.print(
    "[WiFi] Connecting to "
  );

  Serial.println(
    ssid
  );


  WiFi.begin(
    ssid,
    pass
  );


  unsigned long wifiStart =
    millis();


  while (
    WiFi.status() != WL_CONNECTED &&
    millis() - wifiStart < 20000
  )
  {
    delay(500);

    Serial.print(
      "."
    );
  }


  Serial.println();


  if (
    WiFi.status() ==
    WL_CONNECTED
  )
  {
    Serial.println(
      "[WiFi] CONNECTED"
    );

    printWiFiInfo();
  }

  else
  {
    Serial.println(
      "[WiFi] CONNECTION FAILED"
    );

    Serial.println(
      "[WiFi] ESP32 will keep retrying."
    );
  }


  // ----------------------------------------------------------
  // Blynk
  // ----------------------------------------------------------

  Serial.println(
    "[Blynk] Configuring..."
  );


  // IMPORTANT:
  // Blynk.config does not block like Blynk.begin.
  //

  Blynk.config(
    BLYNK_AUTH_TOKEN
  );


  if (
    WiFi.status() ==
    WL_CONNECTED
  )
  {
    Serial.println(
      "[Blynk] Connecting..."
    );


    if (
      Blynk.connect(
        5000
      )
    )
    {
      Serial.println(
        "[Blynk] CONNECTED"
      );
    }
    else
    {
      Serial.println(
        "[Blynk] Not connected."
      );

      Serial.println(
        "[Blynk] Local Flask still works."
      );
    }
  }


  // ----------------------------------------------------------
  // Sensor timer
  // ----------------------------------------------------------

  timer.setInterval(
    SENSOR_INTERVAL,
    readSensor
  );


  // ----------------------------------------------------------
  // Initial display
  // ----------------------------------------------------------

  lcd.clear();

  lcd.setCursor(
    0,
    0
  );

  lcd.print(
    "System Ready"
  );


  lcd.setCursor(
    0,
    1
  );

  lcd.print(
    "Sending to PC"
  );


  Serial.println();
  Serial.println(
    "SYSTEM READY"
  );

  Serial.println(
    "======================================"
  );
}


// ============================================================
// LOOP
// ============================================================

void loop()
{
  // ----------------------------------------------------------
  // Keep WiFi alive
  // ----------------------------------------------------------

  checkWiFi();


  // ----------------------------------------------------------
  // Blynk
  // ----------------------------------------------------------

  if (
    WiFi.status() ==
    WL_CONNECTED
  )
  {
    Blynk.run();
  }


  // ----------------------------------------------------------
  // Timers
  // ----------------------------------------------------------

  timer.run();
}

