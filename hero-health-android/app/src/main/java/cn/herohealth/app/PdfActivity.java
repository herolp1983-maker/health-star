package cn.herohealth.app;

import android.app.Activity;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.graphics.pdf.PdfRenderer;
import android.os.Bundle;
import android.os.ParcelFileDescriptor;
import android.view.Gravity;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.io.File;
import java.nio.file.Files;

public final class PdfActivity extends Activity {
    private PdfRenderer renderer;private ParcelFileDescriptor descriptor;private File temporary;private Bitmap bitmap;private int page;private ImageView image;private TextView counter;private Button previous,next;
    @Override public void onCreate(Bundle state){super.onCreate(state);
        LinearLayout layout=new LinearLayout(this);layout.setOrientation(LinearLayout.VERTICAL);layout.setBackgroundColor(Color.rgb(246,247,251));layout.setPadding(18,42,18,32);setContentView(layout);
        layout.setOnApplyWindowInsetsListener((view,insets)->{int gap=(int)(16*getResources().getDisplayMetrics().density);if(android.os.Build.VERSION.SDK_INT>=30){android.graphics.Insets bars=insets.getInsets(android.view.WindowInsets.Type.systemBars()|android.view.WindowInsets.Type.displayCutout());view.setPadding(gap+bars.left,gap+bars.top,gap+bars.right,gap+bars.bottom);}else{view.setPadding(gap+insets.getSystemWindowInsetLeft(),gap+insets.getSystemWindowInsetTop(),gap+insets.getSystemWindowInsetRight(),gap+insets.getSystemWindowInsetBottom());}return insets;});
        TextView title=new TextView(this);title.setText("报告原件");title.setTextSize(20);layout.addView(title);
        ScrollView scroll=new ScrollView(this);image=new ImageView(this);image.setAdjustViewBounds(true);image.setScaleType(ImageView.ScaleType.FIT_CENTER);scroll.addView(image);layout.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        LinearLayout buttons=new LinearLayout(this);buttons.setGravity(Gravity.CENTER);previous=new Button(this);previous.setText("上一页");next=new Button(this);next.setText("下一页");counter=new TextView(this);counter.setPadding(18,0,18,0);buttons.addView(previous);buttons.addView(counter);buttons.addView(next);layout.addView(buttons);
        Button close=new Button(this);close.setText("返回");close.setOnClickListener(v->finish());layout.addView(close);previous.setOnClickListener(v->{page--;render();});next.setOnClickListener(v->{page++;render();});
        try{HealthVault vault=HealthVault.open(this);String id=getIntent().getStringExtra("reportId");if(!"application/pdf".equals(vault.fileMetadata(id).getString("mime")))throw new Exception();temporary=File.createTempFile("report-",".pdf",getCacheDir());Files.write(temporary.toPath(),vault.attachment(id));descriptor=ParcelFileDescriptor.open(temporary,ParcelFileDescriptor.MODE_READ_ONLY);renderer=new PdfRenderer(descriptor);if(renderer.getPageCount()==0)throw new Exception();render();}catch(Exception error){title.setText("无法预览此 PDF，原件仍保存在档案中。");previous.setEnabled(false);next.setEnabled(false);}
    }
    private void render(){try(PdfRenderer.Page current=renderer.openPage(page)){int width=Math.min(1400,getResources().getDisplayMetrics().widthPixels),height=Math.min(4096,Math.max(1,(int)((double)width*current.getHeight()/current.getWidth())));Bitmap old=bitmap;bitmap=Bitmap.createBitmap(width,height,Bitmap.Config.ARGB_8888);bitmap.eraseColor(Color.WHITE);current.render(bitmap,null,null,PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY);image.setImageBitmap(bitmap);image.setContentDescription("报告第"+(page+1)+"页");if(old!=null)old.recycle();counter.setText((page+1)+" / "+renderer.getPageCount());previous.setEnabled(page>0);next.setEnabled(page+1<renderer.getPageCount());}catch(Exception error){counter.setText("本页无法显示");}}
    @Override protected void onDestroy(){if(renderer!=null)renderer.close();try{if(descriptor!=null)descriptor.close();}catch(Exception ignored){}if(temporary!=null)temporary.delete();if(bitmap!=null)bitmap.recycle();super.onDestroy();}
}
