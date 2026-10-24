package cn.herohealth.app;
import java.util.ArrayList;
import java.util.List;

/** Source geometry only: physical page identity never depends on printed labels. */
final class ImageInputPlan {
    static final int EDGE=2400,OVERLAP=160,MAX_TILES=32;
    static final long MAX_PIXELS=12_000_000L;
    static final class Tile {final int x,y,width,height;Tile(int x,int y,int w,int h){this.x=x;this.y=y;this.width=w;this.height=h;}}
    static boolean elongated(int w,int h){dimensions(w,h);return Math.max(w,h)/(double)Math.min(w,h)>2.5;}
    static int regionSampleSize(int w,int h){dimensions(w,h);int sample=1;while(Math.min(w,h)/sample>1800)sample*=2;return sample;}
    static int sampleSize(int w,int h){
        dimensions(w,h);int sample=1;boolean elongated=Math.max(w,h)/(double)Math.min(w,h)>2.5;
        while((long)Math.max(1,w/sample)*Math.max(1,h/sample)>MAX_PIXELS||(elongated?Math.min(w,h)/sample>1800:Math.max(w,h)/sample>EDGE))sample*=2;
        return sample;
    }
    static int[] renderSize(int w,int h){
        dimensions(w,h);boolean elongated=Math.max(w,h)/(double)Math.min(w,h)>2.5;
        double scale=elongated?Math.min(1800.0/Math.min(w,h),Math.sqrt(MAX_PIXELS/((double)w*h))):2000.0/Math.max(w,h);
        int rw=Math.max(1,(int)(w*scale)),rh=Math.max(1,(int)(h*scale));
        if((long)rw*rh>MAX_PIXELS){if(rw>=rh)rw=(int)(MAX_PIXELS/rh);else rh=(int)(MAX_PIXELS/rw);}
        return new int[]{Math.max(1,rw),Math.max(1,rh)};
    }
    static List<Tile> tiles(int w,int h){
        dimensions(w,h);List<Tile> result=new ArrayList<>();
        for(int y=0;;y+=EDGE-OVERLAP){int th=Math.min(EDGE,h-y);
            for(int x=0;;x+=EDGE-OVERLAP){int tw=Math.min(EDGE,w-x);result.add(new Tile(x,y,tw,th));if(result.size()>MAX_TILES)throw new IllegalArgumentException("图片过长，请拆分或转为多页PDF后导入；未跳过任何图块");if(x+tw>=w)break;}
            if(y+th>=h)break;
        }return result;
    }
    private static void dimensions(int w,int h){if(w<=0||h<=0)throw new IllegalArgumentException("无效图像尺寸");}
}
