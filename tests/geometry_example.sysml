package DemoStructure {

    part def Onshape_Component {
        attribute onshape_url;
    }
    part def Omniverse_Component {
        attribute ov_filepath;
    }
    
    part def Component{
        attribute tx;
        attribute ty;
        attribute tz;

        attribute rx;
        attribute ry;
        attribute rz;
        part children: Component[0..*];
    }

    part def Context {
        part rootmodule :Component {
            part nexus: Onshape_Component,Omniverse_Component subsets children {
                attribute :>> tx=0.0;
                attribute :>> ty=0.0;
                attribute :>> tz=0.0;
                attribute :>> rx=0.0;
                attribute :>> ry=0.0;
                attribute :>> rz=0.0;
                attribute :>> onshape_url = "https://cad.onshape.com/documents/4a29c75993840faff03a0c45/w/64843d9e906f6a84703e03a0/e/fdc17e965aef7326b7f8c27c";
                attribute :>> ov_filepath = "omniverse://localhost/Nexus/nexus.usd";

                part solari_inside_simple: Onshape_Component, Omniverse_Component subsets children {
                    attribute :>> tx=0.5;
                    attribute :>> ty=.0;
                    attribute :>> tz=-10.0;
                    attribute :>> rx=0.0;
                    attribute :>> ry=0.0;
                    attribute :>> rz=0.0;
                    attribute :>> onshape_url = "https://cad.onshape.com/documents/4a29c75993840faff03a0c45/w/64843d9e906f6a84703e03a0/e/6c5f0f56cd58125dcf927c46";
                    attribute :>> ov_filepath = "omniverse://localhost/SolariA/solariA.usd";
                }

                part solari_outside_simple: Onshape_Component,Omniverse_Component subsets children {
                    attribute :>> tx=1.1;
                    attribute :>> ty=5.0;
                    attribute :>> tz=1.0;
                    attribute :>> rx=0.0;
                    attribute :>> ry=0.0;
                    attribute :>> rz=1.57;
                    attribute :>> onshape_url = "https://cad.onshape.com/documents/4a29c75993840faff03a0c45/w/64843d9e906f6a84703e03a0/e/71f0a2750caf9066cb0793fb";
                    attribute :>> ov_filepath = "omniverse://localhost/SolariB/solariB.usd";
                }
            }
        }
    }
}