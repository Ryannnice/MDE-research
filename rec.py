import os, re, ssl, urllib.request
BASE=os.path.dirname(os.path.abspath(__file__)); P=os.path.join(BASE,"papers")
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0 Safari/537.36"
ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
def san(n): return re.sub(r'\s+',' ',re.sub(r'[\\/:*?"<>|]','',n)).strip()[:180]
def dl(url,dest):
    try:
        req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/pdf,*/*"})
        d=urllib.request.urlopen(req,timeout=50,context=ctx).read()
        if d[:5]!=b"%PDF" and b"%PDF" not in d[:3000]: return "not-pdf(%dB)"%len(d)
        open(dest,"wb").write(d); return "OK(%dKB)"%(len(d)//1024)
    except Exception as e: return "ERR:%s"%str(e)[:50]
# ref, folder, title, [candidate urls in priority order]
REC=[
 (3,"02_Applications","SemanticDepth Fusing semantic segmentation and monocular depth estimation for enabling autonomous driving in roads without lane lines",
   ["https://www.mdpi.com/1424-8220/19/14/3224","https://res.mdpi.com/d_attachment/sensors/sensors-19-03224/article_deploy/sensors-19-03224.pdf"]),
 (8,"01_Surveys_and_Reviews","Deep learning for monocular depth estimation A review",
   ["https://eprints.whiterose.ac.uk/168865/1/Deep_Learning_for_Monocular_Depth_Estimation_A_Review.pdf"]),
 (15,"04_Traditional_MachineLearning","Representing shape with a spatial pyramid kernel",
   ["https://www.robots.ox.ac.uk/~vgg/publications/2007/Bosch07/bosch07.pdf"]),
 (18,"04_Traditional_MachineLearning","Conditional random fields Probabilistic models for segmenting and labeling sequence data",
   ["https://repository.upenn.edu/cgi/viewcontent.cgi?article=1162&context=cis_papers"]),
 (30,"03_Traditional_DepthCues","Computing local surface orientation and shape from texture for curved surfaces",
   ["https://www2.eecs.berkeley.edu/Research/Projects/CS/vision/shape/papers/malik_rosenholtz_ijcv97.pdf"]),
 (35,"03_Traditional_DepthCues","Semantic structure from motion",
   ["https://web.eecs.umich.edu/~fouhey/teaching/EECS442_F19/proj4/bao_cvpr11.pdf","https://cvgl.stanford.edu/papers/bao_savarese_cvpr11.pdf"]),
 (39,"04_Traditional_MachineLearning","Depth transfer Depth extraction from video using non-parametric sampling",
   ["https://kevinkarsch.com/wp-content/uploads/2018/09/depthtransfer_pami.pdf","http://kevinkarsch.com/publications/depthtransfer.html"]),
 (46,"07_Self-Supervised","Generative adversarial networks for unsupervised monocular depth prediction",
   ["https://openaccess.thecvf.com/content_ECCVW_2018/papers/11129/Aleotti_Generative_Adversarial_Networks_for_Unsupervised_Monocular_Depth_Prediction_ECCVW_2018_paper.pdf","https://amsacta.unibo.it/id/eprint/6044/1/0337.pdf"]),
 (61,"07_Self-Supervised","Self-supervised learning for monocular depth estimation on minimally invasive surgery scenes",
   ["https://arxiv.org/pdf/2105.13219"]),
 (80,"10_Challenges_Prospects","Chromatic framework for vision in bad weather",
   ["https://www.cs.columbia.edu/CAVE/publications/pdfs/Narasimhan_CVPR00.pdf","https://cave.cs.columbia.edu/old/publications/pdfs/Narasimhan_CVPR00.pdf"]),
 (9,"03_Traditional_DepthCues","Piecewise planar and non-planar stereo for urban scene reconstruction",
   ["https://www.cs.unc.edu/~marc/pubs/GallupCVPR10.pdf"]),
 (5,"02_Applications","Monocular 3d vehicle detection with multi-instance depth and geometry reasoning for autonomous driving",
   ["https://arxiv.org/pdf/2103.15490"]),
 (2,"02_Applications","Depth from motion for smartphone AR",
   ["https://research.google/pubs/pub47785/","https://augmentedperception.github.io/depthfrommotion/depthfrommotion.pdf"]),
]
for num,folder,title,urls in REC:
    dest=os.path.join(P,folder,"[%02d] %s.pdf"%(num,san(title)))
    if os.path.exists(dest) and os.path.getsize(dest)>1500: print("[%02d] skip(exists)"%num); continue
    res="(no candidate worked)"
    for u in urls:
        res=dl(u,dest)
        if res.startswith("OK"): break
    print("[%02d] %s"%(num,res))
