#include <Servo.h>
#define DEBUG(a) Serial.println(a);

//Simple code to control a servomotor thorugh strings sent via serial port

Servo serv;
int servoPin = 9;

void setup()
{
   Serial.begin(9600);
   serv.attach(servoPin);

}

void loop()
{

   if (Serial.available() > 0)
   {
      String str = Serial.readStringUntil('\n');
      int angulo = str.toInt();
      serv.write(angulo);
   }
}