#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>
namespace mb {
inline uint16_t crc(const uint8_t* p,size_t n){uint16_t c=0xffff;while(n--){c^=*p++;for(int i=0;i<8;i++)c=(c&1)?(c>>1)^0xa001:c>>1;}return c;}
inline size_t seal(uint8_t* p,size_t n){auto c=crc(p,n);p[n]=c;p[n+1]=c>>8;return n+2;}
enum class Error {Ok,Timeout,Crc,Frame,Exception,Blocked,Argument,Readback};
struct Result {Error error; uint8_t value=0; uint8_t exception=0; unsigned attempts=0; Result(Error e):error(e){} };
struct Transport {virtual ~Transport(){}; virtual size_t exchange(const uint8_t*,size_t,uint8_t*,size_t,uint32_t)=0;};
class Master {
 Transport& io; uint8_t slave;
 Result transact(uint8_t fc,uint16_t addr,uint16_t value){
  uint8_t q[8]={slave,fc,uint8_t(addr>>8),uint8_t(addr),uint8_t(value>>8),uint8_t(value)};seal(q,6);
  Result out{Error::Timeout};
  for(unsigned attempt=1;attempt<=3;attempt++){
   uint8_t p[16]={};size_t n=io.exchange(q,8,p,sizeof p,300);out.attempts=attempt;
   if(!n){out.error=Error::Timeout;continue;}
   if(n<5){out.error=Error::Frame;continue;}
   if(crc(p,n)!=0){out.error=Error::Crc;continue;}
   if(p[0]!=slave){out.error=Error::Frame;continue;}
   if(p[1]==(fc|0x80)&&n==5){out.error=Error::Exception;out.exception=p[2];return out;}
   if(p[1]!=fc){out.error=Error::Frame;continue;}
   if(fc==5){if(n!=8||memcmp(p,q,8)){out.error=Error::Frame;continue;}}
   else if(n!=6||p[2]!=1){out.error=Error::Frame;continue;}
   out.error=Error::Ok;out.value=p[3];return out;
  }return out;
 }
 public:
 explicit Master(Transport& t,uint8_t id=1):io(t),slave(id){}
 Result read(uint8_t fc){if(fc!=1&&fc!=2)return {Error::Argument};return transact(fc,0,8);}
 Result write(unsigned channel,bool on,bool safe=true){
  if(channel<1||channel>8)return {Error::Argument};
  if(safe)return {Error::Blocked};
  auto w=transact(5,channel-1,on?0xff00:0);if(w.error!=Error::Ok)return w;
  auto r=read(1);if(r.error==Error::Ok&&bool(r.value&(1u<<(channel-1)))!=on)r.error=Error::Readback;
  return r;
 }
};
}

