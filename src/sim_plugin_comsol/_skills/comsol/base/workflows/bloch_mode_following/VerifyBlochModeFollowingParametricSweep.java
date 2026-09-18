import com.comsol.model.*;
import com.comsol.model.util.*;

/** Run two short 3-point Mode-Following sweeps without saving their solutions. */
public class VerifyBlochModeFollowingParametricSweep {
  static final String MODEL = "COMSOL64_3D_Bloch_ModeFollowing_Base.mph";

  static String eigenvalueTag(Model m) throws Exception {
    for (String tag : m.sol("solmf").feature().tags())
      if (m.sol("solmf").feature(tag).getType().equals("Eigenvalue")) return tag;
    throw new Exception("solmf Eigenvalue feature missing");
  }

  static void runAxis(int axis) throws Exception {
    String tag = "ParametricAxis" + axis;
    long start = System.nanoTime();
    Model m = ModelUtil.load(tag, MODEL);
    m.param().set("use_k_scan", "1");
    m.param().set("path_mode", "2");
    m.param().set("path_axis", Integer.toString(axis));
    m.study("stdmf").feature("param").set("plistarr", new String[]{"range(0,1,2)"});
    m.study("stdmf").feature("eig").set("neigs", 8);
    m.sol("solmf").feature(eigenvalueTag(m)).set("neigs", 8);
    m.sol("solmf").runAll();
    if (m.sol("solmf").isEmpty()) throw new Exception("axis " + axis + " sweep is empty");
    double seconds = (System.nanoTime() - start) * 1e-9;
    System.out.println("PARAMETRIC_AXIS=" + axis + " K=range(0,1,2) SECONDS=" + seconds);
    System.out.println("PARAMETRIC_AXIS_" + axis + "=PASS");
    ModelUtil.remove(tag);
  }

  public static void main(String[] args) throws Exception {
    runAxis(0);
    runAxis(1);
    System.out.println("DUAL_PATH_PARAMETRIC_SWEEP=PASS");
  }
}
