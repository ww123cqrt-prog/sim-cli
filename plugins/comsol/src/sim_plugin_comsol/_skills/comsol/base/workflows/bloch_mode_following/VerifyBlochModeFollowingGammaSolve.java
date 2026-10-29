import com.comsol.model.*;
import com.comsol.model.util.*;
import java.util.*;

/**
 * Executable Gamma-point regression for the generic Bloch/Mode-Following base.
 * Loads the delivered model, runs only the manual single-point solver in
 * memory, never saves the solved state, and reports a sentinel after a real
 * matrix assembly and eigensolve.
 */
public class VerifyBlochModeFollowingGammaSolve {
  static String modelPath() {
    return "COMSOL64_3D_Bloch_ModeFollowing_Base.mph";
  }

  static boolean has(String[] values, String expected) {
    return Arrays.asList(values).contains(expected);
  }

  public static void main(String[] args) throws Exception {
    String path = modelPath();
    long start = System.nanoTime();
    Model m = ModelUtil.load("BlochBaseGammaRegression", path);
    System.out.println("BASE_GAMMA_FILE=" + path);
    System.out.println("BASE_GAMMA_PAIRS="
        + Arrays.toString(m.component("comp1").pair().tags()));
    m.param().set("use_k_scan", "0");
    m.param().set("qx", "0");
    m.param().set("qy", "0");
    if (!has(m.sol().tags(), "sol1"))
      throw new Exception("BASE_GAMMA_FAILED: sol1 missing");
    m.sol("sol1").runAll();
    if (m.sol("sol1").isEmpty())
      throw new Exception("BASE_GAMMA_FAILED: sol1 remained empty");
    double seconds = (System.nanoTime() - start) * 1e-9;
    System.out.println("BASE_GAMMA_SOL1_EMPTY=false");
    System.out.println("BASE_GAMMA_SECONDS=" + seconds);
    System.out.println("BASE_GAMMA=PASS");
    ModelUtil.remove("BlochBaseGammaRegression");
  }
}
