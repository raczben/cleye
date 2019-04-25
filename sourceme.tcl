# This TCL script helps to enhance a multi-gig serial link using Xilinx FPGAs.
package require csv
package require struct::matrix

# source sweepValues.tcl

if {![info exists __IBERT_UTIL_SOURCED__]} {
    set __IBERT_UTIL_SOURCED__ 1
} 

# set txDeviceForce {localhost:3121/xilinx_tcf/Digilent/210203A2513BA xc7vx485t_0}

puts "Opening hardware manager"
open_hw

puts "Connect to hardware server"
# Run quietly to prevent errors when it already connected.
connect_hw_server -quiet

proc fetch_devices { } {

    set allDevices ""
    
    puts "Getting hardware targets (ie. blasters)"
    set targets [get_hw_target]

    # Setting XXside (TX/RX) target
    if { [llength $targets] < 1 } {
        puts "No target blaster found. Please connect one to your machine"
        return -1
    } else {
        for {set i 0} {$i < [llength $targets]} {incr i} {
            set trg [lindex $targets $i]
            close_hw_target -quiet
            puts "Opening target for side: $trg"
            # Run quietly to prevent errors when it already opened.
            open_hw_target $trg -quiet
            
            set devices [get_hw_devices]
            for {set j 0} {$j < [llength $devices]} {incr j} {
                set dev [lindex $devices $j]
                # current_hw_device $dev
                lappend allDevices [list $trg $dev]
            }
        }
    }
    puts $allDevices    
    return $allDevices
}

proc set_device { target device } {
    close_hw_target -quiet
    puts "Opening target: $target   $device"
    # Run quietly to prevent errors when it already opened.
    open_hw_target $target -quiet
    current_hw_device $device -quiet
    refresh_hw_device -update_hw_probes false [lindex $device 1]
}



proc choose_device { allDevices side } {
    # Setting XXside (TX/RX) target
    if { [llength $allDevices] < 1 } {
        puts "No devices found. Please connect one and power up."
        return -1
    } elseif { [llength $allDevices] == 1 } {
        return [lindex $allDevices 0]
    } else {        # if { [llength allDevices] > 1 } 
        puts "Please choose a target for $side"
        for {set i 0} {$i < [llength $allDevices]} {incr i} {
            set trg [lindex $allDevices $i]
            puts " [$i] $trg"
        }
        set c [gets stdin]
        return [lindex $allDevices $c]
    }
}


proc fetch_sio { side } {
    set sios [get_hw_sio_gts]

    # Setting Serial Links
    if { [llength $sios] < 1 } {
        puts "ERR: No sio (Serial I/O) found in this device."
        return -1
    } elseif { [llength $sios] == 1 } {
        return [lindex $sios 0]
    } else {        # if { [llength allDevices] > 1 } 
        puts "Please choose sio for $side"
        for {set i 0} {$i < [llength $sios]} {incr i} {
            set sio [lindex $sios $i]
            puts " [$i] $sio"
        }
        set c [gets stdin]
        
        puts $c
        set retVal [lindex $sios $c]
        puts $retVal
        return $retVal
    }
}


proc run_scan { linkName scanFile {hincr 16} {vincr 16} {returnParam "Open Area"} } {
    set xil_newScan [create_hw_sio_scan -description {Scan 4} 2d_full_eye  [lindex [get_hw_sio_links $linkName] 0 ]]
    set_property HORIZONTAL_INCREMENT {$hincr} [get_hw_sio_scans $xil_newScan]
    set_property VERTICAL_INCREMENT {$vincr} [get_hw_sio_scans $xil_newScan]
    run_hw_sio_scan [get_hw_sio_scans $xil_newScan]

    puts "Wait to finish..."
    wait_on_hw_sio_scan $xil_newScan

    write_hw_sio_scan $scanFile [get_hw_sio_scans $xil_newScan] -force

    if { [info commands m]  ne ""} {
        m destroy
    }
    struct::matrix m
    m add columns 3
    set f [open $scanFile]
    csv::read2matrix $f m ,
    close $f
    set rowIdx [lindex [m search all $returnParam] 0 1]
    set openArea [m get cell 1 $rowIdx]
    puts "openArea:  $openArea"
    return $openArea
}


proc create_link { sio } {
    puts "############### create_link ###############"
    puts "#  sio          $sio  #"
    puts "##################################################"

    remove_hw_sio_link [  get_hw_sio_links ]
    set linkName [create_hw_sio_link -description {Link 0} [lindex [get_hw_sio_txs $sio*] 0] [lindex [get_hw_sio_rxs $sio*] 0] ]
    
    return $linkName
}


proc ibert_main {} {
    set allDevices [fetch_devices]

    set txDevice [choose_device $allDevices "TX"]
    set_device $txDevice

    set txSio [choose_sio "TX"]

    set rxDevice [choose_device $allDevices "RX"]
    puts "rxDevice txSio: $txSio"
    close_hw_target -quiet
    puts "close_hw_target txSio: $txSio"
    set_device $rxDevice
    puts "set_device txSio: $txSio"

    set rxSio [choose_sio "RX"]
    puts "rxSio txSio: $txSio"
    puts $rxSio
    puts $txSio

    set links [create_link $txDevice $txSio $rxDevice $rxSio]
    # set txLinkName $rxLinkName
    independent_finder $txDevice [lindex $links 0] $rxDevice [lindex $links 1]
# set xil_newLinks [list]
# set xil_newLink [create_hw_sio_link -description {Link 4} [lindex [get_hw_sio_txs localhost:3121/xilinx_tcf/Digilent/210203A2513BA/0_1_0/IBERT/Quad_113/MGT_X1Y1/TX] 0] [lindex [get_hw_sio_rxs localhost:3121/xilinx_tcf/Digilent/210203A2513BA/0_1_0/IBERT/Quad_113/MGT_X1Y1/RX] 0] ]
# lappend xil_newLinks $xil_newLink
# set xil_newLinkGroup [create_hw_sio_linkgroup -description {Link Group 2} [get_hw_sio_links $xil_newLinks]]
# unset xil_newLinks
}

proc independent_finder {txDevice txLinkName rxDevice rxLinkName} {
    puts "############### independent_finder ###############"
    puts "#  txDevice       $txDevice  #"
    puts "#  txLinkName     $txLinkName  #"
    puts "#  rxDevice       $rxDevice  #"
    puts "#  rxLinkName     $rxLinkName  #"
    puts "##################################################"

    global TXDIFFSWING_values
    global TXPOST_values
    global TXPRE_values

    set globalIteration 1
    set globalParameterSpace {}
    lappend globalParameterSpace [list "TXDIFFSWING" $TXDIFFSWING_values]
    # lappend globalParameterSpace [list "TXPOST" $TXPOST_values]
    # lappend globalParameterSpace [list "TXPRE" $TXPRE_values]
        
    file mkdir runs

    for {set i 0} {$i < $globalIteration} {incr i} {
        foreach paramSpace $globalParameterSpace {
            set pName [lindex $paramSpace 0]
            set pValues [lindex $paramSpace 1]
            
            set openAreas {}
            set maxArea 0
            set_device $txDevice
                puts "############### get_property ###############"
                puts "#  txDevice       $txDevice  #"
                puts "#  txLinkName     $txLinkName  #"
                puts "#  rxDevice       $rxDevice  #"
                puts "#  rxLinkName     $rxLinkName  #"
                puts "#  get_hw_sio_links     [get_hw_sio_links $txLinkName]  #"
                puts "#  pName     $pName  #"
                puts "##################################################"
                
            set bestParam [get_property $pName [get_hw_sio_links $txLinkName]]
            
            foreach pValue $pValues {
                set_device $txDevice
                puts "Create scan ($pName  $pValue)"
                set_property $pName $pValue [get_hw_sio_links $txLinkName]
                commit_hw_sio [get_hw_sio_links $txLinkName]
                
                if {[get_property $pName [get_hw_sio_links $txLinkName]] ne $pValue } {
                    puts "ERROR: Something went wrong. Cannot set value"
                }

                set fname "$i$pName$pValue"
                set fname [regsub -all "\\W" $fname "_"]
                set_device $rxDevice
                set openArea [run_scan $rxLinkName "runs/$fname.csv"]
                
                lappend openAreas $openArea
                
                if { $openArea > $maxArea } {
                    set maxArea $openArea
                    set bestParam $pValue
                }
            }
            
            set_device $txDevice
            puts "pName:  $pName    bestParam:  $bestParam"
            set_property $pName $bestParam [get_hw_sio_links $txLinkName]
            commit_hw_sio [get_hw_sio_links $txLinkName]
        }
    }
}


