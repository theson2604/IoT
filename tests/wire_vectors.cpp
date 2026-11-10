#include "Runtime.h"
#include <stdio.h>
using namespace energy;
int main() {
  puts("{");
  Message m;
  m.sequence=42; m.uptime=1000; m.voltage=12000; m.current=125;
  m.power=1500; m.energy=2; m.status=Status::Simulated;
  m.commandId=7; m.command=CommandType::SetInterval; m.parameter=2000;
  m.interval=2000; m.error=1;
  const char* names[]={"telemetry","command","ack","heartbeat","error"};
  for(unsigned i=1;i<=5;++i) {
    m.type=Type(i);m.device=i==2?2:1;
    uint8_t bytes[MaxPacket];size_t n=serialize(m,bytes,sizeof bytes);
    printf("  \"%s\":\"",names[i-1]);
    for(size_t j=0;j<n;++j)printf("%02x",bytes[j]);
    printf("\"%s\n",i<5?",":"");
  }
  puts("}");
}
