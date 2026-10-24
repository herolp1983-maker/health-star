package cn.herohealth.app;

/** EXIF orientation mapped to the Android Matrix rotation followed by reflection. */
final class ImageOrientation {
    static int degrees(int orientation){switch(orientation){case 3:return 180;case 5:case 6:return 90;case 7:case 8:return -90;default:return 0;}}
    static int scaleX(int orientation){return orientation==2||orientation==5||orientation==7?-1:1;}
    static int scaleY(int orientation){return orientation==4?-1:1;}
    static boolean changes(int orientation){return orientation>=2&&orientation<=8;}
}
