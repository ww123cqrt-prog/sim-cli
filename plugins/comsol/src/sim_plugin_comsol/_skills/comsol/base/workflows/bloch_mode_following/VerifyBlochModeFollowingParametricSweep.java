import com.comsol.model.*;
import com.comsol.model.util.*;
import java.util.*;

/** Run two real 3-point Study-level Mode-Following sweeps without saving them. */
public class VerifyBlochModeFollowingParametricSweep {
  static final String MODEL = "COMSOL64_3D_Bloch_ModeFollowing_Base.mph";
  static final int EXPECTED_POINTS = 3;
  static final int EXPECTED_MODES = 8;

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
    m.study("stdmf").feature("eig").set("neigs", EXPECTED_MODES);
    m.sol("solmf").feature(eigenvalueTag(m)).set("neigs", EXPECTED_MODES);

    // The Study owns the Parametric Sweep. Running solmf directly evaluates only
    // the current parameter value and therefore is not a sweep verification.
    m.study("stdmf").run();

    ArrayList<String> stores = new ArrayList<>();
    ArrayList<Double> kValues = new ArrayList<>();
    ArrayList<Integer> finiteModeCounts = new ArrayList<>();
    for (String solutionTag : m.sol().tags()) {
      if (!m.sol(solutionTag).isEmpty()
          && "ParametricStore".equals(m.sol(solutionTag).getSequenceType())) {
        double[] params = m.sol(solutionTag).getParamVals();
        if (params.length != 1)
          throw new Exception("axis " + axis + " unexpected stored parameters in " + solutionTag);
        int[] size = m.sol(solutionTag).getSize();
        if (size.length == 0 || size[size.length - 1] != EXPECTED_MODES)
          throw new Exception("axis " + axis + " store " + solutionTag
              + " expected " + EXPECTED_MODES + " modes, got " + Arrays.toString(size));
        stores.add(solutionTag);
        kValues.add(params[0]);
        int finite = 0;
        double[] eigenReal = m.sol(solutionTag).getPVals();
        double[] eigenImag = m.sol(solutionTag).getPValsImag();
        for (int i = 0; i < eigenReal.length; i++)
          if (Double.isFinite(eigenReal[i]) && Double.isFinite(eigenImag[i])) finite++;
        finiteModeCounts.add(finite);
      }
    }
    if (stores.size() != EXPECTED_POINTS)
      throw new Exception("axis " + axis + " expected " + EXPECTED_POINTS
          + " ParametricStore solutions, got " + stores.size());
    Collections.sort(kValues);
    for (int i = 0; i < EXPECTED_POINTS; i++)
      if (Math.abs(kValues.get(i) - i) > 1e-12)
        throw new Exception("axis " + axis + " unexpected k stores " + kValues);

    double seconds = (System.nanoTime() - start) * 1e-9;
    System.out.println("PARAMETRIC_AXIS=" + axis + " K=range(0,1,2) POINTS="
        + stores.size() + " REQUESTED_MODES_PER_POINT=" + EXPECTED_MODES
        + " FINITE_TRACKED_MODES=" + finiteModeCounts + " SECONDS=" + seconds);
    System.out.println("PARAMETRIC_AXIS_" + axis + "_EXECUTION=PASS");
    System.out.println("PARAMETRIC_AXIS_" + axis + "_TRACKING_COMPLETENESS="
        + (finiteModeCounts.stream().allMatch(count -> count == EXPECTED_MODES)
            ? "PASS" : "PARTIAL"));
    ModelUtil.remove(tag);
  }

  public static void main(String[] args) throws Exception {
    runAxis(0);
    runAxis(1);
    System.out.println("DUAL_PATH_PARAMETRIC_SWEEP_EXECUTION=PASS");
  }
}
