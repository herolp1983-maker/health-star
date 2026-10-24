package cn.herohealth.app;
import java.util.List;
import org.junit.Test;
import static org.junit.Assert.*;

public class ImageInputPlanTest {
    @Test public void tallImageRetainsReadableWidthRatherThanShrinkingEntireHeight(){
        assertTrue(ImageInputPlan.elongated(1200,12000));assertEquals(1,ImageInputPlan.regionSampleSize(1200,12000));
        List<ImageInputPlan.Tile> tiles=ImageInputPlan.tiles(1200,12000);assertTrue(tiles.size()>1);assertEquals(1200,tiles.get(0).width);
        ImageInputPlan.Tile last=tiles.get(tiles.size()-1);assertEquals(12000,last.y+last.height);
        for(int i=1;i<tiles.size();i++)assertTrue(tiles.get(i).y<tiles.get(i-1).y+tiles.get(i-1).height);
    }
    @Test public void tilesCoverEveryRowAndColumnIncludingLastCorners(){
        int w=5000,h=7000;List<ImageInputPlan.Tile> tiles=ImageInputPlan.tiles(w,h);
        for(int y=0;y<h;y+=97)for(int x=0;x<w;x+=89){boolean covered=false;for(ImageInputPlan.Tile t:tiles)if(x>=t.x&&x<t.x+t.width&&y>=t.y&&y<t.y+t.height)covered=true;assertTrue(covered);}
        ImageInputPlan.Tile last=tiles.get(tiles.size()-1);assertEquals(w,last.x+last.width);assertEquals(h,last.y+last.height);
        for(ImageInputPlan.Tile t:tiles){assertTrue(t.width>0&&t.height>0);assertTrue(t.width<=ImageInputPlan.EDGE&&t.height<=ImageInputPlan.EDGE);}
    }
    @Test public void transposeAndNormalImagesKeepCompleteGeometry(){
        assertEquals(ImageInputPlan.tiles(1200,12000).size(),ImageInputPlan.tiles(12000,1200).size());assertEquals(1,ImageInputPlan.tiles(1600,2200).size());
        assertFalse(ImageInputPlan.elongated(1600,2200));assertEquals(1,ImageInputPlan.sampleSize(1600,2200));
    }
    @Test public void excessiveInputsFailBeforePartialImagePlanIsUsed(){
        assertThrows(IllegalArgumentException.class,()->ImageInputPlan.tiles(1200,1000000));assertThrows(IllegalArgumentException.class,()->ImageInputPlan.tiles(0,100));assertThrows(IllegalArgumentException.class,()->ImageInputPlan.sampleSize(100,-1));
    }
    @Test public void pdfRenderBudgetIsBoundedIncludingExtremeDimensions(){
        for(int[] source:new int[][]{{595,842},{1200,12000},{1,Integer.MAX_VALUE},{Integer.MAX_VALUE,Integer.MAX_VALUE}}){int[] size=ImageInputPlan.renderSize(source[0],source[1]);assertTrue(size[0]>0&&size[1]>0);assertTrue((long)size[0]*size[1]<=ImageInputPlan.MAX_PIXELS);}
    }
}
