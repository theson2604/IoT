#include <Arduino.h>
#include <Modbus.h>
#include <driver/gpio.h>
#ifndef SAFE_DIAGNOSTIC_MODE
#define SAFE_DIAGNOSTIC_MODE 1
#endif
// No guessed direction GPIOs: enable only after bench wiring confirmation.
#ifndef RS485_DE_GPIO
#define RS485_DE_GPIO -1
#endif
#ifndef RS485_RE_GPIO
#define RS485_RE_GPIO -1
#endif
constexpr int de=RS485_DE_GPIO,re=RS485_RE_GPIO;
HardwareSerial bus(1);
bool ready=false;
class Rtu : public mb::Transport {
 size_t exchange(const uint8_t* q,size_t n,uint8_t* p,size_t cap,uint32_t timeout) override {
  if(!ready)return 0;
  // Require 4ms of silence (3.5 characters at 9600 8N1), bounded by timeout.
  uint32_t start=millis(),quiet=micros();
  while(uint32_t(micros()-quiet)<4000){while(bus.available()){bus.read();quiet=micros();}if(uint32_t(millis()-start)>=timeout)return 0;delay(1);}
  digitalWrite(re,HIGH);digitalWrite(de,HIGH);delayMicroseconds(10);
  bus.write(q,n);bus.flush();digitalWrite(de,LOW);digitalWrite(re,LOW);
  size_t used=0;start=millis();uint32_t last=micros();bool overflow=false;
  while(uint32_t(millis()-start)<timeout){
   while(bus.available()){int b=bus.read();if(used<cap)p[used++]=b;else overflow=true;last=micros();}
   if(used&&uint32_t(micros()-last)>=4000)break;
   delayMicroseconds(100);
  }
  return overflow?0:used;
 }
} transport;
mb::Master master(transport);
void report(const char* op,mb::Result r){Serial.printf("%s error=%u bits=0x%02X exception=%u attempts=%u\n",op,unsigned(r.error),r.value,r.exception,r.attempts);}
void command(const char* s){
 if(!ready){Serial.println("BLOCKED: configure and verify DE and /RE GPIOs");return;}
 if(!strcmp(s,"read do"))report("FC01",master.read(1));
 else if(!strcmp(s,"read di"))report("FC02",master.read(2));
 else if(!strcmp(s,"do1 on CONFIRM"))report("FC05+FC01",master.write(1,true,SAFE_DIAGNOSTIC_MODE));
 else if(!strcmp(s,"do1 off CONFIRM"))report("FC05+FC01",master.write(1,false,SAFE_DIAGNOSTIC_MODE));
 else Serial.println("Commands: read do | read di | do1 on CONFIRM | do1 off CONFIRM");
}
bool validDirection(int pin){return pin>=0 && pin<SOC_GPIO_PIN_COUNT && GPIO_IS_VALID_OUTPUT_GPIO(pin);}
void setup(){
 Serial.begin(115200);
 if(!validDirection(de)||!validDirection(re)||de==re||de==TX||de==RX||re==TX||re==RX||de==19||de==20||re==19||re==20)return;
 // Preload low before enabling drivers. Add external DE pull-down for reset safety.
 digitalWrite(de,LOW);digitalWrite(re,LOW);pinMode(de,OUTPUT);pinMode(re,OUTPUT);
 bus.begin(9600,SERIAL_8N1,RX,TX);ready=true;
}
void loop(){
 static char line[64];static size_t used=0;static bool discard=false;
 while(Serial.available()) {char c=Serial.read();if(c=='\r')continue;
 if(c=='\n'){if(!discard){line[used]=0;command(line);}used=0;discard=false;}
 else if(used<sizeof(line)-1&&!discard)line[used++]=c;else discard=true;}
 static uint32_t last=0;if(uint32_t(millis()-last)>=5000){last=millis();Serial.printf("safe=%d ready=%d\n",SAFE_DIAGNOSTIC_MODE,ready);if(ready){report("FC01",master.read(1));report("FC02",master.read(2));}}
 delay(1);
}


