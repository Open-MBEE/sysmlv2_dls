package MyStructure {

    part def Component{
        attribute tx;
        attribute ty;
        attribute tz;

        attribute rx;
        attribute ry;
        attribute rz;

        attribute typeID;
        part children: Component[0..*];
    }


     part def Context {
        part rootelement :Component {
            part nx00001 subsets children {
                attribute :>> tx=1.0;
                attribute :>> ty=1.0;
                attribute :>> tz=1.0;
                attribute :>> rx=1.0;
                attribute :>> ry=1.0;
                attribute :>> rz=1.0;
                attribute :>> typeID = 0;
                part tcs00001 subsets children {
                    attribute :>> tx=1.0;
                    attribute :>> ty=1.0;
                    attribute :>> tz=1.0;
                    attribute :>> rx=1.0;
                    attribute :>> ry=1.0;
                    attribute :>> rz=1.0;
                    attribute :>> typeID = 2;
                }
            }
        }
    }
}
