package cn.herohealth.app;

import org.junit.Test;
import static org.junit.Assert.*;

public class ImageOrientationTest {
    @Test public void portraitClockwiseAndCounterclockwiseAreNormalized(){assertEquals(90,ImageOrientation.degrees(6));assertEquals(-90,ImageOrientation.degrees(8));assertEquals(1,ImageOrientation.scaleX(6));assertEquals(1,ImageOrientation.scaleY(8));}
    @Test public void mirroredExifCasesRetainReflection(){assertEquals(-1,ImageOrientation.scaleX(2));assertEquals(-1,ImageOrientation.scaleY(4));assertEquals(90,ImageOrientation.degrees(5));assertEquals(-1,ImageOrientation.scaleX(5));assertEquals(-90,ImageOrientation.degrees(7));assertEquals(-1,ImageOrientation.scaleX(7));assertEquals(1,ImageOrientation.scaleY(5));}
    @Test public void normalAndUnsupportedTagsLeavePixelsUnchanged(){assertFalse(ImageOrientation.changes(0));assertFalse(ImageOrientation.changes(1));assertFalse(ImageOrientation.changes(9));for(int i=2;i<=8;i++)assertTrue(ImageOrientation.changes(i));assertEquals(180,ImageOrientation.degrees(3));}
}
