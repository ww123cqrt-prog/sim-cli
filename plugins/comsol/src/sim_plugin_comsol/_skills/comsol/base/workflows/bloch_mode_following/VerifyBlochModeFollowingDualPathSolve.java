import com.comsol.model.*;
import com.comsol.model.util.*;
import java.util.*;

/**
 * Small real eigensolve audit for the dual M-Gamma-X/Y-M path contract.
 *
 * The delivered MPH remains unsolved: each anchor is evaluated in a fresh
 * in-memory model and is never saved.  Sorted spectra are compared as sets;
 * solution numbers are not treated as physical mode identities.
 */
public class VerifyBlochModeFollowingDualPathSolve {
  static final String MODEL = "COMSOL64_3D_Bloch_ModeFollowing_Base.mph";

  static double[][] solve(String label, int pathAxis, double pathK) throws Exception {
    String tag = "DualPath" + label.replaceAll("[^A-Za-z0-9]", "");
    long start = System.nanoTime();
    Model m = ModelUtil.load(tag, MODEL);
    m.param().set("use_k_scan", "1");
    m.param().set("path_mode", "2");
    m.param().set("path_axis", Integer.toString(pathAxis));
    m.param().set("k", Double.toString(pathK));
    double qx = m.param().evaluate("qx_active");
    double qy = m.param().evaluate("qy_active");
    m.sol("sol1").runAll();
    String eval = "freqeval";
    m.result().numerical().create(eval, "EvalGlobal");
    m.result().numerical(eval).set("expr", new String[]{"freq"});
    double[][] re = m.result().numerical(eval).getReal();
    double[][] im = m.result().numerical(eval).getImag();
    if (re.length != 1 || re[0].length < 8)
      throw new Exception(label + " returned only " + (re.length == 0 ? 0 : re[0].length)
          + " eigenfrequencies");
    Integer[] order = new Integer[re[0].length];
    for (int i = 0; i < order.length; i++) order[i] = i;
    Arrays.sort(order, Comparator.comparingDouble(i -> re[0][i]));
    double[] sortedRe = new double[order.length], sortedIm = new double[order.length];
    for (int i = 0; i < order.length; i++) {
      sortedRe[i] = re[0][order[i]];
      sortedIm[i] = im[0][order[i]];
    }
    double seconds = (System.nanoTime() - start) * 1e-9;
    ModelUtil.remove(tag);
    System.out.println("DUAL_PATH_POINT=" + label + " axis=" + pathAxis + " k=" + pathK
        + " q=(" + qx + "," + qy + ") seconds=" + seconds);
    System.out.println("DUAL_PATH_FREQ_THz_" + label + "="
        + Arrays.toString(Arrays.stream(sortedRe).map(v -> v / 1e12).toArray()));
    return new double[][]{sortedRe, sortedIm};
  }

  static double maxRelativeSetDifference(double[][] a, double[][] b) throws Exception {
    if (a[0].length != b[0].length) throw new Exception("spectrum lengths differ");
    double out = 0;
    for (int i = 0; i < a[0].length; i++) {
      double scale = Math.max(Math.abs(a[0][i]), Math.abs(b[0][i]));
      out = Math.max(out, Math.abs(a[0][i] - b[0][i]) / scale);
    }
    return out;
  }

  public static void main(String[] args) throws Exception {
    double[][] gammaX = solve("GammaX", 0, 1);
    double[][] gammaY = solve("GammaY", 1, 1);
    double[][] x = solve("X", 0, 2);
    double[][] y = solve("Y", 1, 2);
    double gammaDifference = maxRelativeSetDifference(gammaX, gammaY);
    double xyDifference = maxRelativeSetDifference(x, y);
    System.out.println("DUAL_PATH_GAMMA_MAX_RELATIVE_SET_DIFFERENCE=" + gammaDifference);
    System.out.println("DUAL_PATH_XY_MAX_RELATIVE_SET_DIFFERENCE=" + xyDifference);
    if (gammaDifference > 1e-10)
      throw new Exception("Gamma must be independent of path_axis, difference=" + gammaDifference);
    if (xyDifference < 1e-4)
      throw new Exception("asymmetric pillar failed to distinguish X and Y, difference="
          + xyDifference);
    System.out.println("DUAL_PATH_SOLVE=PASS");
  }
}
