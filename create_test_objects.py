#!/usr/bin/env python3
"""
Script per crear objectes de prova amb formes complexes
"""

import os
from datetime import datetime

def create_test_stp_files():
    """Crea fitxers STP de prova amb formes complexes."""
    
    # Assegurar que existeixen els directoris
    os.makedirs("boxes", exist_ok=True)
    os.makedirs("objects", exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    
    # Crear una caixa hexagonal
    hexagonal_box_content = f"""ISO-10303-21;
HEADER;
/* Generated by PackAssist Test - {timestamp} */
/* Hexagonal Box dimensions: 200 x 173.2 x 100 mm */
FILE_DESCRIPTION(('CAD Model','Hexagonal Box'),'2;1');
FILE_NAME('hexagonal_box.stp','{timestamp}',('PackAssist'),('PackAssist'),'PackAssist v1.0','PackAssist v1.0','Unknown');
FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));
ENDSEC;

DATA;
/* Hexagonal prism vertices */
#1 = CARTESIAN_POINT('',(100.0,0.0,0.0));
#2 = CARTESIAN_POINT('',(50.0,86.6,0.0));
#3 = CARTESIAN_POINT('',(-50.0,86.6,0.0));
#4 = CARTESIAN_POINT('',(-100.0,0.0,0.0));
#5 = CARTESIAN_POINT('',(-50.0,-86.6,0.0));
#6 = CARTESIAN_POINT('',(50.0,-86.6,0.0));

#7 = CARTESIAN_POINT('',(100.0,0.0,100.0));
#8 = CARTESIAN_POINT('',(50.0,86.6,100.0));
#9 = CARTESIAN_POINT('',(-50.0,86.6,100.0));
#10 = CARTESIAN_POINT('',(-100.0,0.0,100.0));
#11 = CARTESIAN_POINT('',(-50.0,-86.6,100.0));
#12 = CARTESIAN_POINT('',(50.0,-86.6,100.0));

#20 = DIRECTION('',(0.0,0.0,1.0));
#21 = DIRECTION('',(1.0,0.0,0.0));
#22 = DIRECTION('',(0.0,1.0,0.0));

#30 = AXIS2_PLACEMENT_3D('',#1,#20,#21);
#31 = GEOMETRIC_REPRESENTATION_CONTEXT(3);
#32 = GEOMETRICALLY_BOUNDED_SURFACE_SHAPE_REPRESENTATION('',(#30),#31);

/* Hexagonal faces and surfaces */
ADVANCED_FACE('',(#1,#2,#3,#4,#5,#6),#31,.T.);
ADVANCED_FACE('',(#7,#8,#9,#10,#11,#12),#31,.T.);

/* Hexagonal box volume: 150000 mm³ */
ENDSEC;
END-ISO-10303-21;
"""

    # Crear un objecte cilíndric
    cylindrical_object_content = f"""ISO-10303-21;
HEADER;
/* Generated by PackAssist Test - {timestamp} */
/* Cylindrical Object dimensions: 80 x 80 x 120 mm */
FILE_DESCRIPTION(('CAD Model','Cylindrical Object'),'2;1');
FILE_NAME('cylindrical_object.stp','{timestamp}',('PackAssist'),('PackAssist'),'PackAssist v1.0','PackAssist v1.0','Unknown');
FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));
ENDSEC;

DATA;
/* Cylindrical surface definition */
#1 = CARTESIAN_POINT('',(0.0,0.0,0.0));
#2 = CARTESIAN_POINT('',(0.0,0.0,120.0));

/* Circle definitions for cylinder */
CIRCLE('base_circle',#1,40.0);
CIRCLE('top_circle',#2,40.0);

/* Cylindrical surface */
CYLINDRICAL_SURFACE('cylinder',#1,40.0);

#10 = DIRECTION('',(0.0,0.0,1.0));
#11 = DIRECTION('',(1.0,0.0,0.0));
#12 = DIRECTION('',(0.0,1.0,0.0));

#20 = AXIS2_PLACEMENT_3D('',#1,#10,#11);
#21 = GEOMETRIC_REPRESENTATION_CONTEXT(3);
#22 = GEOMETRICALLY_BOUNDED_SURFACE_SHAPE_REPRESENTATION('',(#20),#21);

/* Cylindrical object volume: 603185 mm³ */
ENDSEC;
END-ISO-10303-21;
"""

    # Crear un objecte amb corbes complexes
    complex_object_content = f"""ISO-10303-21;
HEADER;
/* Generated by PackAssist Test - {timestamp} */
/* Complex Curved Object dimensions: 150 x 100 x 80 mm */
FILE_DESCRIPTION(('CAD Model','Complex Curved Object'),'2;1');
FILE_NAME('complex_curved_object.stp','{timestamp}',('PackAssist'),('PackAssist'),'PackAssist v1.0','PackAssist v1.0','Unknown');
FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));
ENDSEC;

DATA;
/* Complex curved surface with B-splines */
#1 = CARTESIAN_POINT('',(0.0,0.0,0.0));
#2 = CARTESIAN_POINT('',(75.0,25.0,20.0));
#3 = CARTESIAN_POINT('',(150.0,50.0,40.0));
#4 = CARTESIAN_POINT('',(125.0,75.0,60.0));
#5 = CARTESIAN_POINT('',(50.0,100.0,80.0));

/* B-spline curve definition */
B_SPLINE_CURVE('complex_curve',3,(#1,#2,#3,#4,#5),.UNSPECIFIED.,.F.,.F.);

/* B-spline surface */
B_SPLINE_SURFACE('complex_surface',2,2,((#1,#2,#3),(#2,#3,#4),(#3,#4,#5)),.UNSPECIFIED.,.F.,.F.,.F.);

/* Trimmed curves for complex geometry */
TRIMMED_CURVE('trimmed_1',#1,#3,.T.,.CARTESIAN.);
TRIMMED_CURVE('trimmed_2',#2,#4,.T.,.CARTESIAN.);

#10 = DIRECTION('',(0.0,0.0,1.0));
#11 = DIRECTION('',(1.0,0.0,0.0));
#12 = DIRECTION('',(0.0,1.0,0.0));

#20 = AXIS2_PLACEMENT_3D('',#1,#10,#11);
#21 = GEOMETRIC_REPRESENTATION_CONTEXT(3);
#22 = GEOMETRICALLY_BOUNDED_SURFACE_SHAPE_REPRESENTATION('',(#20),#21);

/* Complex object volume (estimated): 960000 mm³ */
ENDSEC;
END-ISO-10303-21;
"""

    # Crear un objecte triangular
    triangular_object_content = f"""ISO-10303-21;
HEADER;
/* Generated by PackAssist Test - {timestamp} */
/* Triangular Prism Object dimensions: 100 x 86.6 x 50 mm */
FILE_DESCRIPTION(('CAD Model','Triangular Prism'),'2;1');
FILE_NAME('triangular_prism.stp','{timestamp}',('PackAssist'),('PackAssist'),'PackAssist v1.0','PackAssist v1.0','Unknown');
FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));
ENDSEC;

DATA;
/* Triangular prism vertices */
#1 = CARTESIAN_POINT('',(0.0,0.0,0.0));
#2 = CARTESIAN_POINT('',(100.0,0.0,0.0));
#3 = CARTESIAN_POINT('',(50.0,86.6,0.0));

#4 = CARTESIAN_POINT('',(0.0,0.0,50.0));
#5 = CARTESIAN_POINT('',(100.0,0.0,50.0));
#6 = CARTESIAN_POINT('',(50.0,86.6,50.0));

#10 = DIRECTION('',(0.0,0.0,1.0));
#11 = DIRECTION('',(1.0,0.0,0.0));
#12 = DIRECTION('',(0.0,1.0,0.0));

#20 = AXIS2_PLACEMENT_3D('',#1,#10,#11);
#21 = GEOMETRIC_REPRESENTATION_CONTEXT(3);
#22 = GEOMETRICALLY_BOUNDED_SURFACE_SHAPE_REPRESENTATION('',(#20),#21);

/* Triangular faces */
ADVANCED_FACE('',(#1,#2,#3),#21,.T.);
ADVANCED_FACE('',(#4,#5,#6),#21,.T.);

/* Triangular prism volume: 216500 mm³ */
ENDSEC;
END-ISO-10303-21;
"""

    # Escriure els fitxers
    files_to_create = [
        ("boxes/hexagonal_box_200x173x100.stp", hexagonal_box_content),
        ("objects/cylindrical_object_80x80x120.stp", cylindrical_object_content),
        ("objects/complex_curved_object_150x100x80.stp", complex_object_content),
        ("objects/triangular_prism_100x87x50.stp", triangular_object_content)
    ]
    
    created_files = []
    for filepath, content in files_to_create:
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            created_files.append(filepath)
            print(f"✅ Creat: {filepath}")
        except Exception as e:
            print(f"❌ Error creant {filepath}: {e}")
    
    print(f"\n🎯 Fitxers creats: {len(created_files)}")
    print("Aquests fitxers tenen formes complexes per provar la millora de detecció de geometria!")
    
    return created_files

if __name__ == "__main__":
    create_test_stp_files()
